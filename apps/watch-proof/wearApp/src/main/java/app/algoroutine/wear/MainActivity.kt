package app.algoroutine.wear

import android.os.Bundle
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.CoroutineStart
import android.util.AtomicFile
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.wear.compose.material.*
import app.algoroutine.core.*
import java.io.File
import java.io.FileNotFoundException
import java.io.FileOutputStream
import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

private class LocalExecutionStorage(private val file: File) : ExecutionStorage {
    private val atomic = AtomicFile(file)
    override fun read(): StorageRead = try {
        val decoder = Charsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
        StorageRead(decoder.decode(ByteBuffer.wrap(atomic.readFully())).toString(), false)
    } catch (_: FileNotFoundException) {
        StorageRead(null, file.exists() || File(file.path + ".bak").exists())
    } catch (_: Exception) { StorageRead(null, true) }
    override fun write(content: String): Boolean {
        var stream: FileOutputStream? = null
        return try {
            stream = atomic.startWrite()
            stream.write(content.toByteArray(Charsets.UTF_8)); stream.fd.sync()
            atomic.finishWrite(stream); stream = null
            atomic.readFully().contentEquals(content.toByteArray(Charsets.UTF_8))
        } catch (_: Exception) { atomic.failWrite(stream); false }
    }
}

private object ExecutionRepository {
    private val mutex = Mutex()
    suspend fun perform(storage: ExecutionStorage, target: ExecutionView? = null): PersistentExecution =
        withContext(Dispatchers.IO) {
            mutex.withLock {
                val active = PersistentFactory().openDemo(storage)
                if (target != null) active.complete(UUID.randomUUID().toString(), target.currentStepId!!, target.revision)
                active
            }
        }
}

class MainActivity : ComponentActivity() {
    private var createdAt=0L
    private var startupReported=false
    override fun onCreate(savedInstanceState: Bundle?) {
        createdAt=android.os.SystemClock.elapsedRealtime()
        super.onCreate(savedInstanceState)
        DeviceConnection.configureVerification(intent.getIntExtra("verification_port",8791))
        AppLanguage.configure(this,intent.getStringExtra("app_language"))
        val storage = LocalExecutionStorage(File(filesDir, "execution-v1.json"))
        if (DeviceConnection.enabled || intent.getBooleanExtra("demo_server", false)) {
            val session=RemoteSession(this)
            // Local integration measurement only: compare request scheduling in the same binary.
            if(intent.getBooleanExtra("parallel_initial_load",true))lifecycleScope.launch(start=CoroutineStart.UNDISPATCHED){session.request()}
            setContent { RemoteCurrentScreen(this,providedSession=session,onReady={if(!startupReported){startupReported=true;Log.i("RoutineStartup","remote_data_ready_ms=${android.os.SystemClock.elapsedRealtime()-createdAt}")}}) }; return }
        setContent {
            var view by remember { mutableStateOf<ExecutionView?>(null) }
            var error by remember { mutableStateOf<String?>(null) }
            var busy by remember { mutableStateOf(false) }
            val scope = rememberCoroutineScope()
            suspend fun load() {
                busy = true
                val restored = ExecutionRepository.perform(storage)
                view = restored.view(); error = restored.error; busy = false
                Log.i("RoutinePersistence", "restore current=${view?.currentStepId} completed=${view?.completedCount} error=$error")
            }
            LaunchedEffect(Unit) { load() }
            MaterialTheme {
                val target=view
                if(error!=null){Column(Modifier.fillMaxSize().padding(28.dp)){Text(tr("기록을 확인해 주세요"));Button(onClick={scope.launch{load()}}){Text(tr("확인"))}}}
                else if(target!=null&&!target.finished){
                    val items=listOf("open" to tr("문서 열기"),"title" to tr("가제 한 줄 적기"),"keywords" to tr("키워드 세 개 적기")).mapIndexed{i,p->StepView(p.first,p.second,if(i<target.completedCount)"completed" else "pending")}
                    OrbitScreen(parent=target.parentTitle,steps=items,currentId=target.currentStepId,order=items.map{it.id},token="local:${target.revision}",busy=busy,optionsEnabled=false,
                        onAction={kind->if(kind=="complete"&&!busy){busy=true;scope.launch{val active=ExecutionRepository.perform(storage,target);view=active.view();error=active.error;busy=false}}},onRefresh={scope.launch{load()}})
                }else Text(if(target!=null)tr("다음 작업 없음") else tr("불러오는 중"))
            }
        }
    }
}
