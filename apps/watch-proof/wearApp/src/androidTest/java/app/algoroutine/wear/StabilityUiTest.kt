package app.algoroutine.wear

import android.content.Intent
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import java.net.URL
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

/** Repeats the real composition lifecycle against a dedicated active fixture. */
class StabilityUiTest {
 @get:Rule val ui=createEmptyComposeRule()
 private fun expect(s:String){ui.waitUntil(15000){ui.onAllNodesWithText(s).fetchSemanticsNodes().isNotEmpty()}}
 private fun revision()=JSONObject(URL("http://10.0.2.2:8791/context").readText()).getJSONObject("workspace").getInt("revision")
 @Test fun reopenAndRecreateWithoutMutation(){
  val context=InstrumentationRegistry.getInstrumentation().targetContext
  val initial=revision()
  repeat(10){ iteration ->
   ActivityScenario.launch<MainActivity>(Intent(context,MainActivity::class.java).putExtra("demo_server",true).putExtra("app_language","ko")).use { activity ->
    activity.onActivity{it.window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
    expect("문서 열기")
    ui.onNodeWithContentDescription("상세: 문서 열기").performClick()
    ui.onNodeWithText("현재").performClick();expect("문서 열기")
    ui.onRoot().performTouchInput { click(androidx.compose.ui.geometry.Offset(width*.5f,height*.5f)) }
    expect("돌아가기")
    activity.recreate();expect("문서 열기")
    assertEquals("iteration $iteration",initial,revision())
   }
  }
 }
}
