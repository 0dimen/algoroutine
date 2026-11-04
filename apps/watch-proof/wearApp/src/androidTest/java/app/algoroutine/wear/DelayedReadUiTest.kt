package app.algoroutine.wear
import android.content.Intent
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import java.net.URL
import org.json.JSONObject
import org.junit.Rule
import org.junit.Test

/** Requires run_delayed_read_fixture.py and a fresh --active fixture. */
@OptIn(ExperimentalTestApi::class)
class DelayedReadUiTest {
 @get:Rule val ui=createEmptyComposeRule()
 private fun get(path:String)=JSONObject(URL("http://10.0.2.2:8791$path").openConnection().apply{connectTimeout=3000;readTimeout=3000}.getInputStream().bufferedReader().use{it.readText()})
 @Test fun disconnectKeepsSearchDraft(){
  val context=InstrumentationRegistry.getInstrumentation().targetContext
  val before=get("/context").getJSONObject("workspace").getInt("revision")
  ActivityScenario.launch<MainActivity>(Intent(context,MainActivity::class.java).putExtra("demo_server",true).putExtra("app_language","ko")).use{scenario->
   scenario.onActivity{it.window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
   ui.waitUntil(15000){ui.onAllNodesWithText("문서 열기").fetchSemanticsNodes().isNotEmpty()}
   ui.onNodeWithContentDescription("찾기").performClick()
   ui.onNodeWithContentDescription("검색 입력").performClick()
   ui.onNodeWithContentDescription("검색 내용").performScrollTo().performTextInput("보존할 입력")
   get("/test/offline")
   ui.mainClock.advanceTimeBy(2500)
   try{ui.waitUntil(10000){ui.onAllNodesWithText("연결 후 결과 확인").fetchSemanticsNodes().isNotEmpty()}}
   finally{get("/test/online")}
   // Read-only outages recover automatically; do not tap command retry.
   ui.waitUntil(10000){ui.onAllNodesWithContentDescription("검색 내용").fetchSemanticsNodes().isNotEmpty()}
   ui.onNodeWithContentDescription("검색 내용").assertTextEquals("보존할 입력")
   ui.onNodeWithContentDescription("돌아가기").performScrollTo().performClick()
   ui.onNodeWithContentDescription("현재").performClick()
   ui.onRoot().performRotaryScrollInput{rotateToScrollVertically(60f)}
   ui.waitUntil(5000){ui.onAllNodesWithText("가제 적기").fetchSemanticsNodes().isNotEmpty()}
   ui.onNodeWithContentDescription("현재").performClick()
   org.junit.Assert.assertEquals(before,get("/context").getJSONObject("workspace").getInt("revision"))
  }
 }
 @Test fun disconnectRestoresRotaryOnSameScreen(){
  val context=InstrumentationRegistry.getInstrumentation().targetContext
  val before=get("/context").getJSONObject("workspace").getInt("revision")
  ActivityScenario.launch<MainActivity>(Intent(context,MainActivity::class.java).putExtra("demo_server",true).putExtra("app_language","ko")).use{scenario->
   scenario.onActivity{it.window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
   ui.waitUntil(15000){ui.onAllNodesWithText("문서 열기").fetchSemanticsNodes().isNotEmpty()}
   get("/test/offline")
   ui.mainClock.advanceTimeBy(2500)
   try{ui.waitUntil(10000){ui.onAllNodesWithText("연결 후 결과 확인").fetchSemanticsNodes().isNotEmpty()}}
   finally{get("/test/online")}
   // Read-only outages recover automatically; do not tap command retry.
   ui.waitUntil(10000){ui.onAllNodesWithText("연결 후 결과 확인").fetchSemanticsNodes().isEmpty()}
   ui.onRoot().performRotaryScrollInput{rotateToScrollVertically(60f)}
   ui.waitUntil(5000){ui.onAllNodesWithText("가제 적기").fetchSemanticsNodes().isNotEmpty()}
   org.junit.Assert.assertEquals(before,get("/context").getJSONObject("workspace").getInt("revision"))
  }
 }
 @Test fun olderPollCannotUndoAcknowledgedCompletion(){
  val context=InstrumentationRegistry.getInstrumentation().targetContext
  ActivityScenario.launch<MainActivity>(Intent(context,MainActivity::class.java).putExtra("demo_server",true).putExtra("app_language","ko")).use{scenario->
   scenario.onActivity{it.window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
   ui.waitUntil(15000){ui.onAllNodesWithText("문서 열기").fetchSemanticsNodes().isNotEmpty()}
   get("/test/arm")
   ui.mainClock.advanceTimeBy(2500)
   ui.waitUntil(5000){get("/test/status").getBoolean("captured")}
   try {
    ui.onNodeWithContentDescription("완료").performClick()
    ui.waitUntil(3000){ui.onAllNodesWithText("가제 적기").fetchSemanticsNodes().isNotEmpty()}
   } finally {get("/test/release")}
   repeat(15){ui.onAllNodesWithText("문서 열기").assertCountEquals(0);Thread.sleep(100)}
   ui.onNodeWithText("가제 적기").assertExists()
  }
 }
}
