package app.algoroutine.wear
import android.content.Intent
import androidx.activity.compose.setContent
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalFocusManager
import android.graphics.Bitmap
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.io.FileOutputStream
import java.net.URL
import java.net.HttpURLConnection
import java.util.UUID
import org.json.JSONObject
import org.json.JSONArray
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

/** seed_gap_flow.py on a fresh isolated server, adb reverse tcp:8780. */
@OptIn(ExperimentalTestApi::class)
class GapUiTest {
 @get:Rule val ui=createEmptyComposeRule()
 private fun request(path:String,body:JSONObject?=null):String{
  val c=URL("http://127.0.0.1:8780$path").openConnection() as HttpURLConnection;c.connectTimeout=5000;c.readTimeout=5000
  try{if(body!=null){c.requestMethod="POST";c.doOutput=true;c.setRequestProperty("Content-Type","application/json");c.setRequestProperty("X-Routine-App","local");c.outputStream.use{it.write(body.toString().toByteArray())}};assertEquals(200,c.responseCode);return c.inputStream.bufferedReader().use{it.readText()}}finally{c.disconnect()}
 }
 private fun workspace()=JSONObject(request("/api/execution/context")).getJSONObject("workspace")
 private fun expect(text:String){ui.waitUntil(15000){ui.onAllNodesWithText(text).fetchSemanticsNodes().isNotEmpty()}}
 private fun capture(name:String){ui.waitForIdle();val bitmap=ui.onRoot().captureToImage().asAndroidBitmap();FileOutputStream(File(InstrumentationRegistry.getInstrumentation().targetContext.filesDir,"gap-$name.png")).use{bitmap.compress(Bitmap.CompressFormat.PNG,100,it)}}
 /** Fresh seed_ui_flow.py --active fixture; navigational views never change the run. */
 @Test fun idleFutureAndConflictCanRefocus(){
  val initial=workspace();val original=initial.getJSONArray("runs").getJSONObject(0);val d=original.getJSONObject("definition")
  val id=UUID.randomUUID().toString()
  request("/api/execution/command",JSONObject().put("id",UUID.randomUUID().toString()).put("kind","start").put("occurrenceId",id).put("expectedRevision",initial.getInt("revision")).put("definition",d))
  val current=workspace().getJSONArray("runs");val finished=(0 until current.length()).map{current.getJSONObject(it)}.first{it.getString("id")==id}
  assertTrue(JSONObject(request("/api/execution/command",JSONObject().put("id",UUID.randomUUID().toString()).put("kind","completeParent").put("occurrenceId",id).put("expectedRevision",finished.getInt("revision")).put("expectedFocusRevision",workspace().getInt("focusRevision")))).getJSONObject("result").getBoolean("accepted"))
  val before=workspace().toString();val i=InstrumentationRegistry.getInstrumentation()
  ActivityScenario.launch<MainActivity>(Intent(i.targetContext,MainActivity::class.java).putExtra("demo_server",true).putExtra("app_language","ko")).use{scenario->
   scenario.onActivity{it.window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
   expect("다음 작업 없음");capture("idle")
   ui.onNodeWithContentDescription("함께 진행 1").performScrollTo().performClick();expect("함께 진행")
   ui.onNodeWithContentDescription("작업: "+d.getString("title")).assertExists();capture("together")
   ui.onNodeWithContentDescription("현재").performScrollTo().performClick();expect("다음 작업 없음")
   assertEquals(before,workspace().toString())
   val now=System.currentTimeMillis()
   fun reserve(key:String){request("/api/execution/reservations",JSONObject().put("id",key).put("definitionId",d.getString("id")).put("definitionVersion",d.getInt("version")).put("title",d.getString("title")).put("startMillis",now+3600000).put("endMillis",now+7200000))}
   reserve("future-one");ui.mainClock.advanceTimeBy(2500);expect("예약 예정");capture("future")
   ui.onNodeWithContentDescription("함께 진행 1").performScrollTo().assertExists()
   reserve("future-two");ui.mainClock.advanceTimeBy(2500);expect("예약 선택")
   ui.onNodeWithContentDescription("함께 진행 1").performScrollTo().assertExists();capture("conflict-return")
   assertEquals(before,workspace().toString())
   ui.onNodeWithContentDescription("함께 진행 1").performClick()
   ui.onNodeWithContentDescription("작업: "+d.getString("title")).performScrollTo().performClick();expect("문서 열기")
   val after=workspace();assertEquals(original.getString("id"),after.getString("focusId"));assertEquals(2,after.getJSONArray("runs").length())
   assertEquals(original.toString(),(0 until 2).map{after.getJSONArray("runs").getJSONObject(it)}.first{it.getString("id")==original.getString("id")}.toString())
  }
 }
 @Test fun coldStartReplaysPendingOnce(){
  val before=workspace();val runs=before.getJSONArray("runs");val run=(0 until runs.length()).map{runs.getJSONObject(it)}.first{it.getString("id")==before.getString("focusId")}
  val i=InstrumentationRegistry.getInstrumentation();val context=i.targetContext
  val pending=JSONObject().put("id",UUID.randomUUID().toString()).put("kind","complete").put("occurrenceId",run.getString("id")).put("expectedRevision",run.getInt("revision")).put("unitId",run.getString("currentUnitId")).put("expectedFocusRevision",before.getInt("focusRevision"))
  assertTrue(context.getSharedPreferences("remote-execution",0).edit().putString("pending",pending.toString()).commit())
  ActivityScenario.launch<MainActivity>(Intent(context,MainActivity::class.java).putExtra("demo_server",true).putExtra("app_language","ko")).use{scenario->
   scenario.onActivity{it.window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
   expect("가제 적기");val after=workspace();assertEquals(before.getInt("revision")+1,after.getInt("revision"))
   assertFalse(context.getSharedPreferences("remote-execution",0).contains("pending"))
   scenario.recreate();expect("가제 적기");assertEquals(after.toString(),workspace().toString())
  }
 }
 @Test fun unavailableIsNotEmpty(){
  val context=InstrumentationRegistry.getInstrumentation().targetContext
  ActivityScenario.launch<MainActivity>(Intent(context,MainActivity::class.java).putExtra("demo_server",true).putExtra("app_language","ko")).use{scenario->
   scenario.onActivity{it.window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
   expect("일정을 확인할 수 없어요");ui.onAllNodesWithText("다음 작업 없음").assertCountEquals(0)
   ui.onNodeWithContentDescription("새로고침").performScrollTo().assertExists();capture("schedule-unavailable")
  }
 }
 @Test fun supportRotaryRecovers(){
  val enabled=mutableStateOf(true)
  val context=InstrumentationRegistry.getInstrumentation().targetContext
  ActivityScenario.launch<MainActivity>(Intent(context,MainActivity::class.java).putExtra("demo_server",true).putExtra("app_language","ko")).use{scenario->
  scenario.onActivity{activity->activity.window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);activity.setContent{val manager=LocalFocusManager.current
   LaunchedEffect(enabled.value){if(!enabled.value)manager.clearFocus(force=true)}
   SupportPage("함께 진행",enabled=enabled.value){repeat(6){SupportButton("항목 ${it+1}","항목 ${it+1}",enabled.value){}}}
  }}
  ui.onNodeWithText("항목 1").assertIsDisplayed()
  ui.runOnIdle{enabled.value=false};ui.waitForIdle();ui.runOnIdle{enabled.value=true};ui.waitForIdle()
  ui.onRoot().performRotaryScrollInput{rotateToScrollVertically(600f)}
  ui.onNodeWithText("항목 6").assertIsDisplayed()
  }
 }
 @Test fun detailChoiceAndExpiry(){
  val i=InstrumentationRegistry.getInstrumentation()
  ActivityScenario.launch<MainActivity>(Intent(i.targetContext,MainActivity::class.java).putExtra("demo_server",true).putExtra("app_language","ko")).use{scenario->
   scenario.onActivity{it.window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
   expect("예약 선택");val before=workspace();capture("choices")
   ui.onNodeWithContentDescription("예약: 예약 B").performScrollTo().performClick();expect("예약 B")
   assertEquals(before.toString(),workspace().toString());capture("preview")
   ui.onNodeWithContentDescription("예약 목록").performScrollTo().performClick();expect("예약 선택")
   ui.onNodeWithContentDescription("예약: 예약 B").performScrollTo().performClick()
   ui.onNodeWithContentDescription("시작").performScrollTo().performClick();expect("선택한 행동")
   val started=workspace();assertEquals(1,started.getJSONArray("runs").length());assertEquals("reserved-gap-b",started.getString("focusId"))
   val d=started.getJSONArray("runs").getJSONObject(0).getJSONObject("definition")
   request("/api/commands",JSONObject().put("commandId",UUID.randomUUID().toString()).put("kind","saveDefinition").put("definitionId",d.getString("id")).put("expectedVersion",1).put("content",JSONObject().put("title","수정된 원본").put("description","수정된 설명").put("steps",JSONArray().put(JSONObject().put("id","0").put("title","수정된 행동")))))
   ui.onNodeWithContentDescription("상세: 선택한 행동").performClick()
   ui.onNodeWithText(d.getString("author")).performScrollTo().assertExists()
   ui.onNodeWithText("처음 저장한 설명").performScrollTo().assertExists();capture("detail")
   ui.onNodeWithText("2. 다음 단계").performScrollTo().assertExists();capture("steps")
   ui.onNodeWithText("현재").performClick();expect("선택한 행동")
   assertEquals(started.toString(),workspace().toString())
   val all=JSONObject(request("/api/library")).getJSONArray("items");val short=(0 until all.length()).map{all.getJSONObject(it)}.first{it.getString("title")=="짧은 예약"}
   val now=System.currentTimeMillis()
   request("/api/execution/reservations",JSONObject().put("id","gap-short").put("definitionId",short.getString("id")).put("definitionVersion",1).put("title","짧은 예약").put("startMillis",now-1000).put("endMillis",now+12000))
   request("/api/execution/command",JSONObject().put("id",UUID.randomUUID().toString()).put("kind","start").put("occurrenceId","reserved-gap-short").put("expectedRevision",workspace().getInt("revision")).put("definition",JSONObject().put("id",short.getString("id")).put("version",1).put("title","").put("author","").put("steps",JSONArray())))
   ui.mainClock.advanceTimeBy(2500);expect("잠깐 집중");capture("timed")
   ui.waitUntil(20000){ui.mainClock.advanceTimeBy(500);ui.onAllNodesWithContentDescription("시작").fetchSemanticsNodes().isNotEmpty()}
   expect("예약 A");capture("after-expiry")
   val ended=workspace();assertEquals(2,ended.getJSONArray("runs").length());val r=(0 until 2).map{ended.getJSONArray("runs").getJSONObject(it)}.first{it.getString("id")=="reserved-gap-short"}
   assertEquals("elapsed",r.getString("status"));assertEquals(0,r.getInt("completed"));assertEquals(0,r.getInt("skipped"))
   ui.onNodeWithContentDescription("함께 진행 1").assertExists()
  }
 }
}
