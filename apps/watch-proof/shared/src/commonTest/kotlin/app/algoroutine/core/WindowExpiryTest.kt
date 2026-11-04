package app.algoroutine.core
import kotlin.test.*

class WindowExpiryTest {
 private class Disk:ExecutionStorage{var text:String?=null;var fail=false;var commitThenFail=false;override fun read()=StorageRead(text,false);override fun write(content:String):Boolean{if(fail)return false;text=content;return !commitThenFail}}
 private val d=RunDefinition("r",1,"보고서","작성자",listOf(RoutineStep("a","열기"),RoutineStep("b","쓰기"),RoutineStep("c","검토")),10,20,"실행 당시 설명")
 @Test fun boundaryPreservesCompletedAndSkippedButNeverCompletesPending(){
  val disk=Disk();val s=WorkspaceStore(disk)
  s.execute(RunCommand("start","start","one",0,definition=d),10)
  s.execute(RunCommand("complete","complete","one",0,"a",1),11)
  s.execute(RunCommand("skip","skip","one",1,"b",1),12)
  val before=s.view();assertTrue(s.reconcile(19));assertEquals(before,s.view())
  assertTrue(s.reconcile(20));val r=s.view().runs.single()
  assertEquals("elapsed",r.status);assertEquals(listOf("completed","skipped","elapsed"),r.steps.map{it.status});assertNull(r.currentUnitId)
  assertEquals(1,r.completed);assertEquals(1,r.skipped);assertEquals("window_elapsed",r.evidence)
  assertEquals("WINDOW_ELAPSED",s.execute(RunCommand("deadline-tap","complete","one",2,"c",1),20)?.reason)
  val frozen=s.view();val events=s.events();assertTrue(s.reconcile(99));assertEquals(frozen,s.view());assertEquals(events,s.events())
  val reopened=WorkspaceStore(disk);assertEquals(frozen,reopened.view());assertEquals(events,reopened.events())
  assertEquals("실행 당시 설명",reopened.view().runs.single().definition.description)
  // Clock rollback cannot resurrect or complete an already expired run.
  assertEquals("WINDOW_ELAPSED",reopened.execute(RunCommand("late","completeParent","one",r.revision,expectedFocusRevision=1),15)?.reason)
 }
 @Test fun catchUpDoesNotStealFocusOrEndUntimedAndCompletedRuns(){
  val disk=Disk();val s=WorkspaceStore(disk)
  s.execute(RunCommand("a","start","timed",0,definition=d),10)
  s.execute(RunCommand("b","start","done",1,definition=d),10)
  s.execute(RunCommand("c","completeParent","done",0,expectedFocusRevision=2),11)
  s.execute(RunCommand("d","start","untimed",3,definition=d.copy(windowStartMillis=null,windowEndMillis=null)),12)
  val before=s.view();val reopened=WorkspaceStore(disk);assertTrue(reopened.reconcile(100))
  val after=reopened.view();assertEquals(before.focusId,after.focusId);assertEquals(before.focusRevision,after.focusRevision)
  assertEquals(listOf("elapsed","completed","running"),after.runs.map{it.status});assertEquals(1,reopened.events().count{it.kind=="expire"})
 }
 @Test fun failedExpiryDoesNotPublishUnpersistedStateAndAmbiguousWriteReplaysOnce(){
  val disk=Disk();val s=WorkspaceStore(disk);s.execute(RunCommand("s","start","one",0,definition=d),10)
  val before=s.view();disk.fail=true;assertFalse(s.reconcile(20));assertEquals(before,s.view());assertEquals(before,WorkspaceStore(disk).view())
  disk.fail=false;disk.commitThenFail=true;val retry=WorkspaceStore(disk);assertFalse(retry.reconcile(21));assertEquals(before,retry.view())
  disk.commitThenFail=false;val reopened=WorkspaceStore(disk);assertTrue(reopened.reconcile(22));assertEquals(1,reopened.events().count{it.kind=="expire"});assertEquals("elapsed",reopened.view().runs.single().status)
 }
 @Test fun legacyJournalWithoutDescriptionStillLoads(){
  val disk=Disk();val s=WorkspaceStore(disk);s.execute(RunCommand("s","start","one",0,definition=d.copy(description="")),10)
  assertFalse(disk.text!!.contains("description"));assertTrue(disk.text!!.contains("\"schemaVersion\":3"));disk.text=disk.text!!.replace("\"schemaVersion\":3,","");val reopened=WorkspaceStore(disk);assertNull(reopened.error);assertEquals("",reopened.view().runs.single().definition.description)
 }
}
