package app.algoroutine.wear

import android.content.Context
import android.os.SystemClock
import android.util.Log
import androidx.activity.compose.ReportDrawnWhen
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.currentCoroutineContext
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.LocalFocusManager
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.wear.compose.material.*
import app.algoroutine.core.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.*
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

private val wire=Json{ignoreUnknownKeys=true;encodeDefaults=true}
/** Network work must not inherit a Compose frame-clock interceptor. Await remains
 * cancellable; cancelling the owner cancels the isolated IO job (socket deadlines still apply). */
internal suspend fun remoteCall(body:String?=null,path:String?=null):JsonObject=coroutineScope {
    val call=CoroutineScope(Dispatchers.IO).async { remoteBlockingCall(body,path) }
    try { call.await() } finally { call.cancel() }
}
private fun remoteBlockingCall(body:String?,path:String?):JsonObject {
    val started=SystemClock.elapsedRealtime()
    val connection=DeviceConnection.open(path ?: if(body==null)"context" else "command")
    try {connection.connectTimeout=3000;connection.readTimeout=5000
        if(body!=null){connection.requestMethod="POST";connection.doOutput=true;connection.setRequestProperty("Content-Type","application/json");connection.setRequestProperty("X-Routine-App","local");connection.outputStream.use{it.write(body.toByteArray())}}
        check(connection.responseCode==200)
        return wire.parseToJsonElement(connection.inputStream.bufferedReader().use{it.readText()}).jsonObject
    } catch(e:Exception){Log.w("RoutineNetwork","request_failure="+e.javaClass.simpleName);throw e} finally {connection.disconnect();Log.i("RoutineNetwork", "${if(body==null) "read" else "command"}_ms=${SystemClock.elapsedRealtime()-started}")}
}
/** One request owner; cold loading can overlap Compose initialization without replaying commands twice. */
class RemoteSession(context:Context){
    private val prefs by lazy { context.applicationContext.getSharedPreferences(DeviceConnection.pendingStore,Context.MODE_PRIVATE) }
    var snapshot by mutableStateOf<JsonObject?>(null)
    var busy by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
    var readConnectionError=false
    var requestEpoch=0L
    var started=false
    suspend fun request(command:RunCommand?=null){
        if(busy)return;readConnectionError=false;started=true;requestEpoch++;busy=true
        try {
            val pending=withContext(Dispatchers.IO){
                if(command!=null && !prefs.contains("pending"))check(prefs.edit().putString("pending",wire.encodeToString(command)).commit())
                prefs.getString("pending",null)
            }
            val response=remoteCall(pending)
            snapshot=if(pending==null)response else response.getValue("context").jsonObject
            if(pending!=null){withContext(Dispatchers.IO){check(prefs.edit().remove("pending").commit())}}
            error=if(pending!=null&&!response.getValue("result").jsonObject.getValue("accepted").jsonPrimitive.boolean&&response.getValue("result").jsonObject.getValue("reason").jsonPrimitive.content!="WINDOW_ELAPSED")tr("현재 상태를 다시 확인해 주세요") else null
        }catch(cancelled:CancellationException){throw cancelled}
        catch(_:Exception){error=tr("연결 후 결과 확인")}finally{if(currentCoroutineContext().isActive)busy=false}
    }
}

/** Explicit simulator-only integration mode. Local v1 proof remains available without this launch flag. */
@Composable fun RemoteCurrentScreen(context:Context,onReady:()->Unit={},providedSession:RemoteSession?=null){
    val session=providedSession ?: remember{RemoteSession(context)}
    val scope=rememberCoroutineScope()
    val keyboard=LocalSoftwareKeyboardController.current;val focusManager=LocalFocusManager.current
    LaunchedEffect(session.error){if(session.error!=null){keyboard?.hide();focusManager.clearFocus(force=true)}}
    val hostView=LocalView.current
    LaunchedEffect(session){
        if(!session.started)session.request()
        while(isActive){
            delay(2000)
            if(hostView.hasWindowFocus()&&!session.busy&&(session.error==null||session.readConnectionError)){
                val readEpoch=session.requestEpoch
                try {val next=remoteCall();if(!session.busy&&readEpoch==session.requestEpoch){session.snapshot=next;if(session.readConnectionError){session.error=null;session.readConnectionError=false}}}
                catch(cancelled:CancellationException){throw cancelled}
                catch(_:Exception){if(isActive&&!session.busy&&readEpoch==session.requestEpoch){session.readConnectionError=true;session.error=tr("연결 후 결과 확인")}}
            }
        }
    }
    val ready=session.snapshot!=null&&!session.busy&&session.error==null
    ReportDrawnWhen{ready}
    LaunchedEffect(ready){if(ready)onReady()}


    var together by remember{mutableStateOf(false)}
    var inspectedId by remember{mutableStateOf<String?>(null)}
    var finding by remember{mutableStateOf(false)}
    MaterialTheme(colors=MaterialTheme.colors.copy(background=Color.White,onBackground=Color(0xFF14243D),primary=Color(0xFF17365E),onPrimary=Color.White)){CompositionLocalProvider(LocalContentColor provides Color(0xFF14243D)){Box(Modifier.fillMaxSize().background(Color.White)){
        val data=session.snapshot
        if(session.error!=null&&data==null){Column(Modifier.fillMaxSize().padding(32.dp),horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.Center){Text(session.error!!,color=Color(0xFF14243D),fontSize=14.sp,textAlign=TextAlign.Center);Spacer(Modifier.height(10.dp));Button(onClick={scope.launch{session.request()}},enabled=!session.busy){Text(tr("확인"),fontSize=14.sp,color=Color.White)}}}
        else if(data!=null){Box(Modifier.fillMaxSize().then(if(session.error!=null)Modifier.clearAndSetSemantics{} else Modifier)){
            val w=wire.decodeFromJsonElement<WorkspaceView>(data.getValue("workspace"));val now=data.getValue("serverNow").jsonPrimitive.long
            val run=w.runs.firstOrNull{it.id==w.focusId};val active=run!=null&&run.status=="running"&&(run.definition.windowEndMillis==null||now<run.definition.windowEndMillis!!)
            val others=w.runs.filter{it.id!=w.focusId&&it.status=="running"&&(it.definition.windowEndMillis==null||now<it.definition.windowEndMillis!!)}
            if(finding){FindRoutineScreen(busy=session.busy||session.error!=null,onBack={finding=false},onStart={d->scope.launch{
                session.request(RunCommand(UUID.randomUUID().toString(),"start",UUID.randomUUID().toString(),w.revision,definition=d))
                if(session.error==null)finding=false
            }})}
            else if(together){
                val inspected=others.firstOrNull{it.id==inspectedId}
                if(inspected!=null){APage(backLabel=tr("돌아가기"),back={inspectedId=null},actionLabel=tr("집중하기"),enabled=!session.busy,action={scope.launch{session.request(RunCommand(UUID.randomUUID().toString(),"focus",inspected.id,w.revision));if(session.error==null){together=false;inspectedId=null}}}){
                    Text(inspected.definition.title,color=AInk,fontSize=19.sp);ASource(inspected.definition.author)
                    inspected.steps.forEachIndexed{i,n->Text((if(n.status=="completed")"✓" else "${i+1}")+" · "+n.title,color=AInk,fontSize=14.sp,modifier=Modifier.fillMaxWidth().background(ASubtle).padding(10.dp))}
                }}else{APage(backLabel=tr("현재"),back={together=false;inspectedId=null},actionLabel=tr("현재"),action={together=false;inspectedId=null}){
                    Text(tr("함께 진행"),color=AInk,fontSize=19.sp)
                    if(others.isEmpty())Text(tr("함께 진행 중인 작업 없음"),color=ASlate)
                    others.forEach{r->AStepRow("›",r.definition.title){inspectedId=r.id}}
                }}
            }
            else if(active&&run!=null){OrbitScreen(parent=run.definition.title,steps=run.steps,currentId=run.currentUnitId,order=run.order,token="${run.id}:${run.revision}:${w.focusRevision}",busy=session.busy||session.error!=null,author=run.definition.author,description=run.definition.description,
                windowStart=run.definition.windowStartMillis,windowEnd=run.definition.windowEndMillis,now=now,otherCount=others.size,onOthers={together=true},onFind={finding=true},
                onAction={kind->scope.launch{session.request(RunCommand(UUID.randomUUID().toString(),kind,run.id,run.revision,if(kind=="completeParent")null else run.currentUnitId,w.focusRevision))}},onRefresh={scope.launch{session.request()}})}
            else{
                val selected=wire.decodeFromJsonElement<ReservationSelection>(data.getValue("reservation"))
                val item=selected.candidates.singleOrNull()
                if(selected.state=="conflict")ReservationChoices(selected.candidates,now,session.busy||session.error!=null,onFind={finding=true},otherCount=others.size,onOthers={together=true},onStart={r->scope.launch{session.request(RunCommand(UUID.randomUUID().toString(),"start",r.occurrenceId!!,w.revision,definition=RunDefinition(r.definitionId,r.definitionVersion,r.title,"",emptyList())))}})
                else if(item!=null&&now>=item.startMillis)OrbitScreen(parent=item.title,steps=emptyList(),currentId=null,order=emptyList(),token=item.id,busy=session.busy||session.error!=null,windowStart=item.startMillis,windowEnd=item.endMillis,now=now,primary=tr("시작"),optionsEnabled=false,otherCount=others.size,onOthers={together=true},onFind={finding=true},onAction={scope.launch{session.request(RunCommand(UUID.randomUUID().toString(),"start",item.occurrenceId!!,w.revision,definition=RunDefinition(item.definitionId,item.definitionVersion,item.title,"",emptyList())))}},onRefresh={scope.launch{session.request()}})
                else SupportPage(if(selected.state=="none")tr("다음 작업 없음") else item?.title ?: tr("일정을 확인할 수 없어요"),enabled=!session.busy&&session.error==null){
                    if(item!=null){Text(orbitTimes(item.startMillis,item.endMillis),fontSize=12.sp);Text(tr("예약 예정"),fontSize=13.sp)}
                    SupportButton("⌕",tr("찾기"),!session.busy){finding=true}
                    if(others.isNotEmpty())SupportButton("+${others.size}",tr("함께 진행 {count}", "count" to others.size),!session.busy){together=true}
                    SupportButton("↻",tr("새로고침"),!session.busy){scope.launch{session.request()}}
                }

            }
        }}else Box(Modifier.fillMaxSize(),contentAlignment=Alignment.Center){Text(tr("불러오는 중"),fontSize=14.sp)}
        if(session.error!=null&&data!=null){Column(Modifier.fillMaxSize().background(Color.White.copy(alpha=.97f)).clickable{}.padding(32.dp),horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.Center){Text(session.error!!,color=Color(0xFF14243D),fontSize=14.sp,textAlign=TextAlign.Center);Spacer(Modifier.height(10.dp));Button(onClick={scope.launch{session.request()}},enabled=!session.busy,modifier=Modifier.size(112.dp,44.dp)){Text(tr("결과 확인"),fontSize=12.sp,color=Color.White)}}}
    }}
}
}
