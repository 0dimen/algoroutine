package app.algoroutine.core
import kotlin.test.*

class WorkspaceTest {
    private val d=RunDefinition("report",1,"보고서 초안 시작","작성자",listOf(RoutineStep("a","문서 열기"),RoutineStep("b","가제 적기"),RoutineStep("c","키워드 적기")))
    private fun start(e:WorkspaceEngine,id:String="one")=e.execute(RunCommand("start-$id","start",id,e.view().revision,definition=d),1)
    private fun cmd(e:WorkspaceEngine,kind:String,id:String="c-$kind"):RunCommand {
        val v=e.view();val r=v.runs.first{it.id==v.focusId};return RunCommand(id,kind,r.id,r.revision,if(kind=="completeParent")null else r.currentUnitId,v.focusRevision)
    }
    @Test fun deferIsImmediatelyAfterNextNotLast() {
        val e=WorkspaceEngine();start(e);e.execute(cmd(e,"defer"),2)
        assertEquals(listOf("b","a","c"),e.view().runs[0].order);assertEquals("b",e.view().runs[0].currentUnitId);assertEquals(0,e.view().runs[0].completed)
        e.execute(cmd(e,"complete"),3);assertEquals("a",e.view().runs[0].currentUnitId)
    }
    @Test fun lastPendingCannotBeDeferred() {
        val e=WorkspaceEngine();start(e);repeat(2){e.execute(cmd(e,"complete","$it"),2)}
        assertEquals("NO_NEXT_UNIT",e.execute(cmd(e,"defer"),3).reason)
    }
    @Test fun skippedIsNeverAutomaticallyCompleted() {
        val e=WorkspaceEngine();start(e);e.execute(cmd(e,"skip"),2)
        repeat(2){e.execute(cmd(e,"complete","$it"),3)}
        val r=e.view().runs[0];assertEquals("exhausted",r.status);assertEquals(2,r.completed);assertEquals(1,r.skipped);assertNull(r.evidence)
    }
    @Test fun parentCompletionExcludesButDoesNotFabricateChildCompletions() {
        val e=WorkspaceEngine();start(e);e.execute(cmd(e,"complete"),2);e.execute(cmd(e,"completeParent"),3)
        val r=e.view().runs[0];assertEquals("completed",r.status);assertEquals("direct_parent",r.evidence);assertEquals(listOf("completed","excluded","excluded"),r.steps.map{it.status})
    }
    @Test fun allChildrenAutoCompleteParent() {
        val e=WorkspaceEngine();start(e);repeat(3){e.execute(cmd(e,"complete","$it"),2)}
        assertEquals("required_children",e.view().runs[0].evidence)
        assertEquals(4,e.events().size)
    }
    @Test fun focusRoundTripPreservesProgressAndRejectsStaleAction() {
        val e=WorkspaceEngine();start(e);e.execute(cmd(e,"complete"),2)
        val stale=cmd(e,"skip");val original=e.view().runs[0];start(e,"two")
        e.execute(RunCommand("focus","focus","one",e.view().revision),3)
        assertEquals(original,e.view().runs[0]);assertEquals("FOCUS_CHANGED",e.execute(stale,4).reason)
        assertEquals("a",e.view().runs[1].currentUnitId)
    }
    @Test fun duplicateCommandsAcrossKindsAndRunsDoNotMutate() {
        val e=WorkspaceEngine();val result=start(e);val v=e.view()
        assertEquals(result,e.execute(RunCommand("start-one","start","one",0,definition=d),100))
        assertEquals("COMMAND_CONFLICT",e.execute(RunCommand("start-one","focus","two",1),101).reason)
        assertEquals(v,e.view())
    }
    private class Disk:ExecutionStorage {var text:String?=null;var fail=false;override fun read()=StorageRead(text,false);override fun write(content:String):Boolean {if(fail)return false;text=content;return true}}
    @Test fun wholeWorkspaceRestoresReceiptsFocusAndOrderAtomically() {
        val disk=Disk();val s=WorkspaceStore(disk);val start=RunCommand("s","start","one",0,definition=d)
        val receipt=s.execute(start,1);s.execute(RunCommand("d","defer","one",0,"a",1),2)
        val before=s.view();val reopened=WorkspaceStore(disk)
        assertEquals(before,reopened.view());assertEquals(receipt,reopened.execute(start,99));assertEquals(before,reopened.view())
        disk.fail=true;assertNull(reopened.execute(RunCommand("c","complete","one",1,"b",1),3));assertEquals(before,reopened.view())
        assertEquals(before,WorkspaceStore(disk).view())
    }
    @Test fun corruptWorkspaceRemainsUntouched() {val disk=Disk();disk.text="bad";val s=WorkspaceStore(disk);assertNotNull(s.error);assertNull(s.execute(RunCommand("s","start","one",0,definition=d),1));assertEquals("bad",disk.text)}
    @Test fun elapsedWindowIsReadOnlyAndNeverCompletesItself() {
        val e=WorkspaceEngine();val timed=d.copy(windowStartMillis=10,windowEndMillis=20)
        assertEquals("EARLY_START",e.execute(RunCommand("early","start","one",0,definition=timed),9).reason)
        assertTrue(e.execute(RunCommand("start","start","one",0,definition=timed),10).accepted)
        val before=e.view();assertEquals("WINDOW_ELAPSED",e.execute(cmd(e,"complete"),20).reason)
        assertEquals(before,e.view());assertEquals("running",e.view().runs.single().status)
        assertEquals("WINDOW_ELAPSED",e.execute(cmd(e,"completeParent"),21).reason)
    }
    @Test fun definitionEditsCannotChangeRunningSnapshot() {val e=WorkspaceEngine();val steps=d.steps.toMutableList();e.execute(RunCommand("mutable","start","one",0,definition=d.copy(steps=steps)),1);steps[0]=RoutineStep("a","수정");assertEquals("문서 열기",e.view().runs[0].steps[0].title)}
}
class ScheduleSelectorTest {
    private val s=ScheduleSelector();private val a=Reservation("a","d",1,"현재",10,20);private val b=Reservation("b","e",1,"다음",20,30)
    @Test fun halfOpenBoundaryAndFutureSelection() {assertEquals(a,s.select(listOf(a,b),10,true).candidates.single());assertEquals(b,s.select(listOf(a,b),20,true).candidates.single());assertEquals("none",s.select(listOf(a,b),30,true).state)}
    @Test fun conflictsAndIncompleteReadsAreNotEmpty() {assertEquals("conflict",s.select(listOf(a,a.copy(id="x")),11,true).state);assertEquals("conflict",s.select(listOf(b,b.copy(id="x")),0,true).state);assertEquals("unavailable",s.select(emptyList(),0,false).state)}
}
