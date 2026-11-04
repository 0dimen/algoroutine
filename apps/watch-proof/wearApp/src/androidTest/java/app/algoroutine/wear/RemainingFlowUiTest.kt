@file:OptIn(androidx.compose.ui.test.ExperimentalTestApi::class)
package app.algoroutine.wear

import android.content.Intent
import androidx.activity.compose.setContent
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Density
import android.graphics.Bitmap
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

/** Only connects to the dedicated disposable verification profile, never 8791. */
class RemainingFlowUiTest {
 @get:Rule val ui=createEmptyComposeRule()
 private fun api(path:String,body:JSONObject?=null):JSONObject{
  val c=URL("http://10.0.2.2:8793$path").openConnection() as HttpURLConnection
  c.connectTimeout=5000;c.readTimeout=10000
  try{if(body!=null){c.requestMethod="POST";c.doOutput=true;c.setRequestProperty("Content-Type","application/json");c.setRequestProperty("X-Routine-App","local");c.outputStream.use{it.write(body.toString().toByteArray())}};assertEquals(200,c.responseCode);return JSONObject(c.inputStream.bufferedReader().use{it.readText()})}finally{c.disconnect()}
 }
 private fun workspace()=api("/context").getJSONObject("workspace")
 private fun mode(value:String){api("/__mode",JSONObject().put("mode",value))}
 private fun desc(s:String)=ui.onNodeWithContentDescription(s)
 private fun waitText(s:String,timeout:Long=15000){ui.waitUntil(timeout){ui.mainClock.advanceTimeBy(250);ui.onAllNodesWithText(s).fetchSemanticsNodes().isNotEmpty()}}
 private fun waitDesc(s:String){ui.waitUntil(15000){ui.mainClock.advanceTimeBy(250);ui.onAllNodesWithContentDescription(s).fetchSemanticsNodes().isNotEmpty()}}
 private fun capture(name:String){ui.waitForIdle();Thread.sleep(250);val i=InstrumentationRegistry.getInstrumentation();FileOutputStream(File(i.targetContext.filesDir,"remaining-$name.png")).use{i.uiAutomation.takeScreenshot().compress(Bitmap.CompressFormat.PNG,100,it)};File(i.targetContext.filesDir,"remaining-$name.txt").writeText(ui.onRoot().printToString())}
 private fun launch(name:String,language:String="en",block:(ActivityScenario<MainActivity>)->Unit){
  api("/__reset",JSONObject().put("scenario",name))
  val c=InstrumentationRegistry.getInstrumentation().targetContext
  c.getSharedPreferences("remote-execution-verification-8793",0).edit().clear().commit()
  ActivityScenario.launch<MainActivity>(Intent(c,MainActivity::class.java).putExtra("demo_server",true).putExtra("verification_port",8793).putExtra("app_language",language)).use{s->s.onActivity{it.window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)};block(s)}
  mode("normal")
 }
 @Test fun concurrentPreviewFocusReturn(){launch("concurrent"){scenario->
  waitText("Write heading");val before=workspace();capture("concurrent-current")
  desc(tr("함께 진행 {count}","count" to 1)).performClick();waitText("Reset focus");capture("concurrent-list")
  desc("Reset focus").performClick();waitText(tr("집중하기"));capture("concurrent-preview");ui.onNodeWithText("2 · Choose next action").performScrollTo().assertExists();capture("concurrent-preview-scrolled")
  assertEquals(before.toString(),workspace().toString())
  desc(tr("집중하기")).performClick();waitText("Take one breath");capture("concurrent-other")
  assertEquals("other",workspace().getString("focusId"));assertEquals(before.getJSONArray("runs").toString(),workspace().getJSONArray("runs").toString())
  desc(tr("함께 진행 {count}","count" to 1)).performClick();waitText("Report draft");desc("Report draft").performClick();capture("concurrent-original-preview")
  desc(tr("집중하기")).performClick();waitText("Write heading");capture("concurrent-return")
  val after=workspace();assertEquals("original",after.getString("focusId"));assertEquals(before.getJSONArray("runs").toString(),after.getJSONArray("runs").toString());assertEquals(before.getInt("revision")+2,after.getInt("revision"))
  scenario.recreate();waitText("Write heading");assertEquals(after.toString(),workspace().toString());capture("concurrent-recreated")
 }}
 @Test fun gestureDeferSkipParentCompletion(){launch("gesture"){
  waitText("Open document");val before=workspace().getInt("revision")
  ui.onRoot().performTouchInput{down(Offset(width*.5f,height*.78f))};ui.mainClock.advanceTimeBy(500);waitDesc(tr("미루기"));capture("hold")
  ui.onRoot().performTouchInput{up()};waitDesc(tr("찾기"));assertEquals(before,workspace().getInt("revision"))
  ui.onRoot().performTouchInput{down(Offset(width*.5f,height*.78f))};ui.mainClock.advanceTimeBy(500);waitDesc(tr("미루기"))
  ui.onRoot().performTouchInput{moveTo(Offset(width*.5f,height*.38f));up()};waitText("Write heading");capture("deferred")
  desc(tr("완료")).performClick();waitText("Open document")
  ui.onRoot().performTouchInput{click(Offset(width*.5f,height*.5f))};waitDesc(tr("건너뛰기"));desc(tr("건너뛰기")).performClick();waitText("List key points");capture("skipped")
  ui.onRoot().performTouchInput{swipe(Offset(width*.2f,height*.5f),Offset(width*.8f,height*.5f),400)};waitText("Report draft");capture("parent")
  desc(tr("완료")).performClick();waitText(tr("다음 작업 없음"));capture("parent-completed")
  val r=workspace().getJSONArray("runs").getJSONObject(0);assertEquals("completed",r.getString("status"));assertEquals(1,r.getInt("skipped"));assertEquals(1,r.getInt("completed"));assertEquals("direct_parent",r.getString("evidence"))
 }}
 @Test fun reservationsPreviewAndDetails(){launch("conflict"){
  waitText(tr("예약 선택"));val before=workspace();capture("reservation-conflict")
  desc(tr("예약: {title}","title" to "Reset focus")).performScrollTo().performClick();waitText("Reset focus");capture("reservation-preview");assertEquals(before.toString(),workspace().toString())
  desc(tr("시작")).performScrollTo().performClick();waitText("Take one breath");capture("reservation-started")
  assertEquals("reserved-choice-b",workspace().getString("focusId"))
  desc(tr("상세: {title}","title" to "Take one breath")).performClick();desc(tr("돌아가기")).performClick()
  ui.onNodeWithText("Choose next action").performScrollTo().assertExists();capture("full-detail")
  ui.onNodeWithText("Pause and choose a concrete next action.").performScrollTo().assertExists();capture("detail-description")
  desc(tr("현재")).performClick();waitText("Take one breath")
 }}
 @Test fun timedExpiryDoesNotCompleteOrAutoStart(){launch("timed"){
  waitText("Take one breath");ui.onRoot().performTouchInput{swipe(Offset(width*.2f,height*.5f),Offset(width*.8f,height*.5f),400)};waitText("Reset focus");capture("timed-running")
  ui.waitUntil(60000){ui.mainClock.advanceTimeBy(250);ui.onAllNodesWithText("Next reservation").fetchSemanticsNodes().isNotEmpty()};capture("timed-expired-next")
  val w=workspace();assertEquals(1,w.getJSONArray("runs").length());val r=w.getJSONArray("runs").getJSONObject(0)
  assertEquals("elapsed",r.getString("status"));assertEquals(0,r.getInt("completed"));assertEquals(0,r.getInt("skipped"));desc(tr("시작")).assertExists()
 }}
 @Test fun connectionRecoveryAndLostResponse(){launch("active"){
  waitText("Open document");val before=workspace().getInt("revision");mode("read_error")
  waitText(tr("결과 확인"));capture("connection-error");mode("normal")
  ui.waitUntil(15000){ui.mainClock.advanceTimeBy(250);ui.onAllNodesWithContentDescription(tr("완료")).fetchSemanticsNodes().isNotEmpty()};capture("connection-recovered")
  assertEquals(before,workspace().getInt("revision"))
  mode("drop_command_once");desc(tr("완료")).performClick();waitText(tr("연결 후 결과 확인"));capture("lost-response")
  ui.onNodeWithText(tr("결과 확인")).performClick();waitText("Write heading");assertEquals(before+1,workspace().getInt("revision"));capture("lost-response-replayed")
 }}
 @Test fun emptyAndFutureAreDistinct(){launch("empty"){
  waitText(tr("다음 작업 없음"));capture("empty");assertEquals(0,workspace().getJSONArray("runs").length())
 };launch("future"){
  waitText("Next reservation");waitText(tr("예약 예정"));capture("future");ui.onAllNodesWithContentDescription(tr("시작")).assertCountEquals(0);assertEquals(0,workspace().getJSONArray("runs").length())
 }}
 @Test fun longKoreanTitleAndSearchFailure(){launch("long-ko","ko"){
  val title="보고서 초안을 시작하기 위해 새 문서를 열고 첫 문장을 준비하기";waitText(title)
  desc(tr("상세: {title}","title" to title)).performClick();capture("long-korean-detail");ui.onRoot().performRotaryScrollInput{rotateToScrollVertically(100f)};capture("long-korean-scrolled");desc(tr("현재")).performClick()
  mode("search_error");desc(tr("찾기")).performClick();waitText(tr("연결을 확인해 주세요"));capture("search-error");mode("normal");desc(tr("다시")).performClick()
  waitDesc(tr("검색 입력"));desc(tr("검색 입력")).performClick();desc(tr("검색 내용")).performScrollTo().performTextInput("qzxv987654")
  desc(tr("찾기")).performClick();waitText(tr("맞는 루틴이 없어요"));capture("search-empty")
  desc(tr("더 자세하게")).performClick();desc(tr("검색 내용")).performScrollTo().assertTextEquals("qzxv987654");capture("search-input-preserved")
 }}
 @Test fun enlargedTextKeepsDetailsAndReturnReachable(){launch("concurrent"){scenario->
  waitText("Write heading")
  scenario.onActivity{a->a.setContent{CompositionLocalProvider(LocalDensity provides Density(LocalDensity.current.density,1.3f)){RemoteCurrentScreen(a)}}}
  waitText("Write heading");capture("font-130-current")
  desc(tr("상세: {title}","title" to "Write heading")).performClick();capture("font-130-detail")
  desc(tr("현재")).assertIsDisplayed();desc(tr("돌아가기")).performClick()
  ui.onNodeWithText("List key points").performScrollTo().assertExists();capture("font-130-scroll")
  desc(tr("현재")).assertIsDisplayed();desc(tr("현재")).performClick();waitText("Write heading");ui.mainClock.advanceTimeBy(500);capture("font-130-return");desc(tr("찾기")).performTouchInput{click()};waitDesc(tr("검색 입력"));capture("font-130-find")
 }}

}
