package app.algoroutine.wear
import android.content.Intent
import android.graphics.Bitmap
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.geometry.Offset
import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.io.FileOutputStream
import java.net.URL
import java.net.HttpURLConnection
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

/** A fresh, explicitly seeded integration occurrence. Never resets existing user data. */
@OptIn(ExperimentalTestApi::class)
class OrbitUiTest {
 @get:Rule val ui=createEmptyComposeRule()
 private fun expect(text:String){ui.waitUntil(15000){ui.onAllNodesWithText(text).fetchSemanticsNodes().isNotEmpty()}}
 private fun command(c:JSONObject){val conn=URL("http://10.0.2.2:8791/command").openConnection() as HttpURLConnection;conn.requestMethod="POST";conn.doOutput=true;conn.setRequestProperty("Content-Type","application/json");conn.setRequestProperty("X-Routine-App","local");conn.outputStream.use{it.write(c.toString().toByteArray())};assertEquals(200,conn.responseCode);conn.inputStream.close();conn.disconnect()}
 private fun revision():Int=JSONObject(URL("http://10.0.2.2:8791/context").readText()).getJSONObject("workspace").getInt("revision")
 private fun capture(name:String){val i=InstrumentationRegistry.getInstrumentation();FileOutputStream(File(i.targetContext.filesDir,"orbit-$name.png")).use{i.uiAutomation.takeScreenshot().compress(Bitmap.CompressFormat.PNG,100,it)}}
 private fun down(){ui.waitForIdle();ui.onRoot().performTouchInput{down(Offset(width*.5f,height*.78f))};ui.mainClock.advanceTimeBy(500)}
 private fun move(x:Float,y:Float){ui.onRoot().performTouchInput{moveTo(Offset(width*x,height*y))}}
 private fun release(){ui.onRoot().performTouchInput{up()}}
 @Test fun orbitGesturesAndCancellation(){val i=InstrumentationRegistry.getInstrumentation()
  ActivityScenario.launch<MainActivity>(Intent(i.targetContext,MainActivity::class.java).putExtra("demo_server",true).putExtra("app_language","ko")).use {scenario->
   scenario.onActivity{it.window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
   expect("문서 열기");var initial=revision();capture("current")
   // External focus round-trip while a finger is held invalidates the original contact.
   down();ui.onNodeWithContentDescription("미루기").assertExists()
   val old=JSONObject(URL("http://10.0.2.2:8791/context").readText()).getJSONObject("workspace")
   val oldId=old.getString("focusId");val all=old.getJSONArray("runs");val active=(0 until all.length()).map{all.getJSONObject(it)}.first{it.getString("id")==oldId}
   val temp="touch-"+System.currentTimeMillis()
   command(JSONObject().put("id",temp).put("kind","start").put("occurrenceId",temp).put("expectedRevision",initial).put("definition",active.getJSONObject("definition")))
   command(JSONObject().put("id",temp+"-back").put("kind","focus").put("occurrenceId",oldId).put("expectedRevision",initial+1))
   // Advance the Compose test clock through the real two-second refresh interval.
   ui.mainClock.advanceTimeBy(2500)
   ui.waitUntil(10000){ui.onAllNodesWithContentDescription("미루기").fetchSemanticsNodes().isEmpty()};release();expect("문서 열기");assertEquals(initial+2,revision());initial+=2
   // Up/down are read-only peer browsing; primary becomes return-to-current.
   ui.onRoot().performTouchInput{swipe(Offset(width*.75f,height*.65f),Offset(width*.75f,height*.35f),400)}
   expect("가제 적기");expect("탐색 중");assertEquals(initial,revision());capture("browse")
   ui.onNodeWithContentDescription("현재").performClick();expect("문서 열기")
   ui.onRoot().performRotaryScrollInput{rotateToScrollVertically(60f)};expect("가제 적기");expect("탐색 중");assertEquals(initial,revision())
   ui.onNodeWithContentDescription("현재").performClick();expect("문서 열기")
   // A long hold without moving is cancelled, never a delayed completion.
   down();ui.onNodeWithContentDescription("미루기").assertExists();capture("hold");release();expect("문서 열기");assertEquals(initial,revision())
   // Sliding outside all three targets cancels as well.
   down();ui.onNodeWithContentDescription("미루기").assertExists();move(.5f,.60f);release();assertEquals(initial,revision())
   // Middle action is defer: next step first, previous step immediately after it.
   down();ui.onNodeWithContentDescription("미루기").assertExists();move(.5f,.38f);expect("미루기");capture("defer");release();expect("가제 적기")
   assertEquals(initial+1,revision())
   ui.onNodeWithContentDescription("완료").performClick();expect("문서 열기")
   // Horizontal navigation reaches real parent with child satellites, without execution.
   val after=revision();ui.onRoot().performTouchInput{swipe(Offset(width*.25f,height*.5f),Offset(width*.75f,height*.5f),400)}
   expect("보고서 초안 시작");capture("parent");assertEquals(after,revision())
   ui.onRoot().performTouchInput{swipe(Offset(width*.75f,height*.5f),Offset(width*.25f,height*.5f),400)};expect("문서 열기")
   // Right option skips this occurrence's child; it is not recorded as complete.
   down();ui.onNodeWithContentDescription("미루기").assertExists();ui.onRoot().performTouchInput{moveTo(Offset(width*.5f+104f,height*.38f))};expect("건너뛰기");release();expect("키워드 적기")
   ui.onNodeWithContentDescription("완료").performClick();expect("다음 작업 없음");capture("next")
   val c=JSONObject(URL("http://10.0.2.2:8791/context").readText()).getJSONObject("workspace")
   val runs=c.getJSONArray("runs");val r=(0 until runs.length()).map{runs.getJSONObject(it)}.first{it.getString("id")==c.getString("focusId")}
   assertEquals("exhausted",r.getString("status"));assertEquals(1,r.getInt("skipped"));assertEquals(2,r.getInt("completed"))
  }
 }
 @Test fun longTitleCanBeReadInDetails(){val i=InstrumentationRegistry.getInstrumentation();val title="보고서 초안을 시작하기 위해 새 문서를 열고 첫 문장을 준비하기"
  ActivityScenario.launch<MainActivity>(Intent(i.targetContext,MainActivity::class.java).putExtra("demo_server",true).putExtra("app_language","ko")).use {scenario->
   scenario.onActivity{it.window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
   expect(title);capture("long-title")
   ui.onNodeWithContentDescription("상세: $title").performClick();expect(title);capture("long-detail")
   ui.onNodeWithText("현재").performClick();expect(title)
  }
 }

}
