package app.algoroutine.wear
import android.content.Intent
import android.graphics.Bitmap
import java.io.File
import java.io.FileOutputStream
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import java.net.URL
import java.net.HttpURLConnection
import java.util.UUID
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

/** Fresh isolated server prepared by scripts/seed_ui_flow.py. No user-data reset. */
@OptIn(ExperimentalTestApi::class)
class FullFlowUiTest {
 @get:Rule val ui=createEmptyComposeRule()
 private fun expect(s:String){try{ui.waitUntil(15000){ui.onAllNodesWithText(s).fetchSemanticsNodes().isNotEmpty()}}catch(e:Throwable){android.util.Log.e("RoutineTestFailure","Missing expected node: $s",e);runCatching{ui.onRoot().printToLog("RoutineTestFailure")};runCatching{capture("failure")};throw e}}
 private fun api(path:String,body:JSONObject?=null):JSONObject {
  val c=URL("http://127.0.0.1:8780$path").openConnection() as HttpURLConnection
  c.connectTimeout=5000;c.readTimeout=5000
  try{if(body!=null){c.requestMethod="POST";c.doOutput=true;c.setRequestProperty("Content-Type","application/json");c.setRequestProperty("X-Routine-App","local");c.outputStream.use{it.write(body.toString().toByteArray())}};assertEquals(200,c.responseCode);return JSONObject(c.inputStream.bufferedReader().use{it.readText()})}finally{c.disconnect()}
 }
 private fun capture(name:String){val i=InstrumentationRegistry.getInstrumentation();val bitmap=i.uiAutomation.takeScreenshot();if(bitmap==null){android.util.Log.w("RoutineTest","Screenshot unavailable: $name");return};FileOutputStream(File(i.targetContext.filesDir,"flow-$name.png")).use{bitmap.compress(Bitmap.CompressFormat.PNG,100,it)}}
 private fun workspace()=api("/api/execution/context").getJSONObject("workspace")
 @Test fun mobileDefinitionStartRefocusAndRestore(){
  val i=InstrumentationRegistry.getInstrumentation();val intent=Intent(i.targetContext,MainActivity::class.java).putExtra("demo_server",true).putExtra("app_language","ko")
  var original="";var before=0
  ActivityScenario.launch<MainActivity>(intent).use { scenario ->
   scenario.onActivity{it.window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
   expect("통합 검증 루틴");ui.onNodeWithContentDescription("시작").performClick();expect("문서 열기")
   original=workspace().getString("focusId")
   ui.onNodeWithContentDescription("완료").performClick();expect("가제 적기")
   val items=api("/api/library").getJSONArray("items");val other=(0 until items.length()).map{items.getJSONObject(it)}.first{it.getString("title")=="함께 진행 검증"}
   val d=JSONObject().put("id",other.getString("id")).put("version",other.getInt("version")).put("title",other.getString("title")).put("author","").put("steps",other.getJSONArray("steps"))
   api("/api/execution/command",JSONObject().put("id",UUID.randomUUID().toString()).put("kind","start").put("occurrenceId",UUID.randomUUID().toString()).put("expectedRevision",workspace().getInt("revision")).put("definition",d))
   expect("호흡 고르기");ui.onNodeWithContentDescription("함께 진행 1").performClick();expect("통합 검증 루틴")
   ui.onNodeWithText("통합 검증 루틴").performClick();expect("가제 적기")
   assertEquals(original,workspace().getString("focusId"));before=workspace().getInt("revision")
  }
  // Activity closure and relaunch, plus a separate process restoration phase below.
  ActivityScenario.launch<MainActivity>(intent).use { scenario ->
   scenario.onActivity{it.window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
   expect("가제 적기");assertEquals(before,workspace().getInt("revision"));capture("restored")
   ui.onNodeWithContentDescription("완료").performClick();expect("키워드 적기")
  }
 }
 @Test fun processRestoresAndFinishes(){
  val i=InstrumentationRegistry.getInstrumentation();val before=workspace();val id=before.getString("focusId")
  ActivityScenario.launch<MainActivity>(Intent(i.targetContext,MainActivity::class.java).putExtra("demo_server",true).putExtra("app_language","ko")).use { scenario ->
   scenario.onActivity{it.window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
   expect("키워드 적기");assertEquals(before.getInt("revision"),workspace().getInt("revision"));capture("process-restored")
   ui.onNodeWithContentDescription("완료").performClick();expect("다음 작업 없음");capture("finished")
   val runs=workspace().getJSONArray("runs");val r=(0 until runs.length()).map{runs.getJSONObject(it)}.first{it.getString("id")==id}
   assertEquals(3,r.getInt("completed"));assertEquals(0,r.getInt("skipped"));assertEquals("completed",r.getString("status"))
  }
 }
 @Test fun liveRecommendationCompleteAndReturn(){
  val i=InstrumentationRegistry.getInstrumentation()
  ActivityScenario.launch<MainActivity>(Intent(i.targetContext,MainActivity::class.java).putExtra("demo_server",true).putExtra("app_language","ko")).use { scenario ->
   scenario.onActivity{it.window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
   val initial=workspace();val runs=initial.getJSONArray("runs")
   val focused=(0 until runs.length()).map{runs.getJSONObject(it)}.first{it.getString("id")==initial.getString("focusId")}
   val original=(0 until runs.length()).map{runs.getJSONObject(it)}.first{it.getString("id")=="voice-original"}.toString()
   assertNotEquals("voice-original",focused.getString("id"))
   val d=focused.getJSONObject("definition");val steps=d.getJSONArray("steps");assertTrue(steps.length()>0)
   expect(steps.getJSONObject(0).getString("title"));capture("live-recommendation-start")
   ui.onNodeWithContentDescription("함께 진행 1").performClick();expect("기존 진행 루틴")
   ui.onNodeWithText("기존 진행 루틴").performClick();expect("기존 행동");capture("live-return-original")
   ui.onNodeWithContentDescription("함께 진행 1").performClick();expect(d.getString("title"))
   ui.onNodeWithText(d.getString("title")).performClick()
   for(index in 0 until steps.length()){
    expect(steps.getJSONObject(index).getString("title"));capture("live-step-$index")
    ui.onNodeWithContentDescription("완료").performClick()
   }
   expect("다음 예약");capture("live-next-reservation")
   val end=workspace().getJSONArray("runs");val all=(0 until end.length()).map{end.getJSONObject(it)}
   assertEquals(original,all.first{it.getString("id")=="voice-original"}.toString())
   val done=all.first{it.getString("id")==focused.getString("id")}
   assertEquals("completed",done.getString("status"));assertEquals(steps.length(),done.getInt("completed"))
   assertFalse(all.any{it.getString("id")=="reserved-voice-next"})
  }
 }

 @Test fun mobileVoiceStartCompleteAndReturn(){
  val i=InstrumentationRegistry.getInstrumentation()
  ActivityScenario.launch<MainActivity>(Intent(i.targetContext,MainActivity::class.java).putExtra("demo_server",true).putExtra("app_language","ko")).use { scenario ->
   scenario.onActivity{it.window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
   expect("모바일 첫 행동")
   fun original()=(0 until workspace().getJSONArray("runs").length()).map{workspace().getJSONArray("runs").getJSONObject(it)}.first{it.getString("id")=="voice-original"}.toString()
   val old=original();capture("voice-mobile-start")
   ui.onNodeWithContentDescription("함께 진행 1").performClick();expect("기존 진행 루틴")
   ui.onNodeWithText("기존 진행 루틴").performClick();expect("기존 행동");capture("voice-return-original")
   ui.onNodeWithContentDescription("함께 진행 1").performClick();expect("음성으로 시작한 루틴")
   ui.onNodeWithText("음성으로 시작한 루틴").performClick();expect("모바일 첫 행동")
   ui.onNodeWithContentDescription("완료").performClick();expect("모바일 다음 행동");capture("voice-next-step")
   ui.onNodeWithContentDescription("완료").performClick();expect("다음 예약");capture("voice-next-reservation")
   assertEquals(old,original())
   val runs=workspace().getJSONArray("runs")
   val generated=(0 until runs.length()).map{runs.getJSONObject(it)}.first{it.getString("id")=="voice-generated"}
   assertEquals("completed",generated.getString("status"));assertEquals(2,generated.getInt("completed"))
   assertFalse((0 until runs.length()).any{runs.getJSONObject(it).getString("id")=="reserved-voice-next"})
  }
 }

 @Test fun findStartAndReturn(){
  val i=InstrumentationRegistry.getInstrumentation()
  ActivityScenario.launch<MainActivity>(Intent(i.targetContext,MainActivity::class.java).putExtra("demo_server",true).putExtra("app_language","ko")).use { scenario ->
   scenario.onActivity{it.window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
   expect("통합 검증 루틴");ui.onNodeWithContentDescription("시작").performClick();expect("문서 열기")
   ui.onNodeWithContentDescription("완료").performClick();expect("가제 적기")
   val before=workspace();val original=before.getString("focusId")
   val old=(0 until before.getJSONArray("runs").length()).map{before.getJSONArray("runs").getJSONObject(it)}.first{it.getString("id")==original}.toString()
   ui.onNodeWithContentDescription("찾기").performClick();expect("함께 진행 검증")
   ui.onRoot().performTouchInput{swipeUp()};ui.onRoot().performTouchInput{swipeUp()}
   ui.onNodeWithContentDescription("루틴: 보고서 초안 시작").assertExists()
   ui.onRoot().performTouchInput{swipeDown()};ui.onRoot().performTouchInput{swipeDown()}
   ui.onNodeWithContentDescription("루틴: 함께 진행 검증").performClick();expect("1. 호흡 고르기")
   ui.onNodeWithText("2. 한 줄 정리").performScrollTo().assertExists()
   assertEquals(before.getInt("revision"),workspace().getInt("revision"))
   capture("find-detail")
   ui.onNodeWithContentDescription("시작").performScrollTo().performClick();expect("호흡 고르기")
   val started=workspace();assertEquals(before.getJSONArray("runs").length()+1,started.getJSONArray("runs").length())
   val prior=(0 until started.getJSONArray("runs").length()).map{started.getJSONArray("runs").getJSONObject(it)}.first{it.getString("id")==original}
   assertEquals(old,prior.toString());capture("find-started")
   ui.onNodeWithContentDescription("함께 진행 1").performClick();expect("통합 검증 루틴")
   ui.onNodeWithText("통합 검증 루틴").performClick();expect("가제 적기")
   val returned=workspace();assertEquals(original,returned.getString("focusId"))
   assertEquals(old,(0 until returned.getJSONArray("runs").length()).map{returned.getJSONArray("runs").getJSONObject(it)}.first{it.getString("id")==original}.toString())
   capture("find-returned")
   ui.onNodeWithContentDescription("찾기").performClick();expect("함께 진행 검증")
   ui.onNodeWithContentDescription("현재").performClick();expect("가제 적기")
   assertEquals(returned.getInt("revision"),workspace().getInt("revision"))
  }
 }

 @Test fun deckNavigationDoesNotStart(){
  val i=InstrumentationRegistry.getInstrumentation()
  ActivityScenario.launch<MainActivity>(Intent(i.targetContext,MainActivity::class.java).putExtra("demo_server",true).putExtra("app_language","ko")).use {
   expect("통합 검증 루틴");val before=workspace().getInt("revision")
   ui.onNodeWithContentDescription("찾기").performClick();expect("추천")
   expect("함께 진행 검증");ui.onNodeWithContentDescription("루틴: 함께 진행 검증").assertExists();capture("deck-first")
   ui.onRoot().performTouchInput{swipeUp()};expect("통합 검증 루틴");capture("deck-second")
   ui.onRoot().performRotaryScrollInput{rotateToScrollVertically(-60f)};expect("함께 진행 검증")
   ui.onNodeWithContentDescription("검색 입력").performClick();expect("어떤 루틴을 찾으세요?")
   ui.onNodeWithContentDescription("검색 내용").performScrollTo().performTextInput("호흡")
   ui.onNodeWithContentDescription("돌아가기").performScrollTo().performClick();expect("추천")
   ui.onNodeWithContentDescription("검색 입력").performClick()
   ui.onNodeWithContentDescription("검색 내용").assertTextEquals("호흡")
   assertEquals(before,workspace().getInt("revision"))
  }
 }
 @Test fun textSearchReviewStartReturn(){
  val i=InstrumentationRegistry.getInstrumentation()
  ActivityScenario.launch<MainActivity>(Intent(i.targetContext,MainActivity::class.java).putExtra("demo_server",true).putExtra("app_language","ko")).use { scenario ->
   scenario.onActivity{it.window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
   expect("통합 검증 루틴");ui.onNodeWithContentDescription("시작").performClick();expect("문서 열기")
   ui.onNodeWithContentDescription("완료").performClick();expect("가제 적기")
   val before=workspace();val original=before.getString("focusId")
   ui.onNodeWithContentDescription("찾기").performClick();expect("추천")
   ui.onNodeWithContentDescription("검색 입력").performClick();expect("어떤 루틴을 찾으세요?")
   ui.onNodeWithContentDescription("검색 내용").performScrollTo().performTextInput("우주선 정비")
   assertEquals(before.getInt("revision"),workspace().getInt("revision"))
   ui.onNodeWithContentDescription("찾기").performScrollTo().performClick();expect("맞는 루틴이 없어요")
   ui.onNodeWithContentDescription("더 자세하게").performClick()
   ui.onNodeWithContentDescription("검색 내용").performScrollTo().performTextReplacement("호흡")
   ui.onNodeWithContentDescription("찾기").performScrollTo().performClick();expect("함께 진행 검증")
   ui.onNodeWithContentDescription("루틴: 함께 진행 검증").assertExists()
   capture("search-result")
   assertEquals(before.getInt("revision"),workspace().getInt("revision"))
   ui.onNodeWithContentDescription("루틴: 함께 진행 검증").performClick();expect("1. 호흡 고르기")
   ui.onNodeWithContentDescription("시작").performScrollTo().performClick();expect("호흡 고르기")
   ui.onNodeWithContentDescription("함께 진행 1").performClick();expect("통합 검증 루틴")
   ui.onNodeWithText("통합 검증 루틴").performClick();expect("가제 적기")
   assertEquals(original,workspace().getString("focusId"));capture("search-returned")
  }
 }

}
