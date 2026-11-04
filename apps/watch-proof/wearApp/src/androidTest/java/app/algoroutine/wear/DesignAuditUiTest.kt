@file:OptIn(androidx.compose.ui.test.ExperimentalTestApi::class)
package app.algoroutine.wear

import android.content.Intent
import android.graphics.Bitmap
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.io.FileOutputStream
import java.net.URL
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

/** Visual audit of a running local fixture. Never invokes an execution command. */
class DesignAuditUiTest {
 @get:Rule val ui=createEmptyComposeRule()
 private fun revision()=JSONObject(URL("http://10.0.2.2:8791/context").readText()).getJSONObject("workspace").getInt("revision")
 private fun desc(value:String)=ui.onNodeWithContentDescription(value)
 private fun waitDesc(value:String){ui.waitUntil(15000){ui.onAllNodesWithContentDescription(value).fetchSemanticsNodes().isNotEmpty()}}
 private fun shot(name:String){
  ui.waitForIdle();InstrumentationRegistry.getInstrumentation().waitForIdleSync();Thread.sleep(350)
  val i=InstrumentationRegistry.getInstrumentation()
  FileOutputStream(File(i.targetContext.filesDir,"design-audit-$name.png")).use{i.uiAutomation.takeScreenshot().compress(Bitmap.CompressFormat.PNG,100,it)}
  File(i.targetContext.filesDir,"design-audit-$name.txt").writeText(ui.onRoot().printToString())
 }
 @Test fun readOnlyScreenInventory(){
  val context=InstrumentationRegistry.getInstrumentation().targetContext
  val before=revision()
  ActivityScenario.launch<MainActivity>(Intent(context,MainActivity::class.java).putExtra("demo_server",true).putExtra("app_language","en")).use{scenario->
   scenario.onActivity{it.window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
   waitDesc("Find");shot("current")
   ui.onRoot().performTouchInput{down(Offset(width*.5f,height*.78f))}
   ui.mainClock.advanceTimeBy(500);waitDesc("Later");shot("held-options")
   ui.onRoot().performTouchInput{up()};waitDesc("Find")
   ui.onNode(hasContentDescription("Details:",substring=true)).performClick();shot("detail")
   desc("Back").performClick();shot("routine-current-detail")
   ui.onRoot().performRotaryScrollInput{rotateToScrollVertically(80f)};shot("detail-scrolled")
   ui.onNodeWithText("Current",useUnmergedTree=true).performClick();waitDesc("Done")
   ui.onRoot().performTouchInput{click(Offset(width*.5f,height*.5f))};shot("options")
   ui.onRoot().performTouchInput{click(Offset(width*.5f,height*.62f))};waitDesc("Find")
   desc("Find").performClick();waitDesc("Enter a request")
   ui.waitUntil(15000){ui.onAllNodes(hasContentDescription("Routine:",substring=true)).fetchSemanticsNodes().isNotEmpty()};shot("find");desc("Start").assertIsDisplayed()
   ui.onRoot().performRotaryScrollInput{rotateToScrollVertically(60f)};shot("find-next")
   ui.onNode(hasContentDescription("Routine:",substring=true)).performClick();shot("routine-detail");desc("Start").assertIsDisplayed()
   desc("Find").performClick();waitDesc("Enter a request")
   desc("Enter a request").performClick();shot("input")
  }
  assertEquals("Read-only audit must preserve execution revision",before,revision())
 }
}
