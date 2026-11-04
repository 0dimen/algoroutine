package app.algoroutine.wear
import android.content.Intent
import android.graphics.Bitmap
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.io.FileOutputStream
import org.junit.Rule
import org.junit.Test
class IntegrationUiTest {
    @get:Rule val ui=createEmptyComposeRule()
    private fun expect(text:String){ui.waitUntil(15000){ui.onAllNodesWithText(text).fetchSemanticsNodes().isNotEmpty()};ui.onNodeWithText(text).assertExists()}
    @Test fun sharedRoutineCompletesAndAdvances(){
        val i=InstrumentationRegistry.getInstrumentation()
        ActivityScenario.launch<MainActivity>(Intent(i.targetContext,MainActivity::class.java).putExtra("demo_server",true).putExtra("app_language","ko")).use {
            expect("문서 열기")
            ui.onNodeWithContentDescription("완료").performClick();expect("가제 적기")
            FileOutputStream(File(i.targetContext.filesDir,"integration-current.png")).use {o->i.uiAutomation.takeScreenshot().compress(Bitmap.CompressFormat.PNG,100,o)}
            ui.onNodeWithContentDescription("완료").performClick();expect("키워드 적기")
            ui.onNodeWithContentDescription("완료").performClick();expect("다음 작업 없음")
            FileOutputStream(File(i.targetContext.filesDir,"integration-next.png")).use {o->i.uiAutomation.takeScreenshot().compress(Bitmap.CompressFormat.PNG,100,o)}
        }
    }
}
