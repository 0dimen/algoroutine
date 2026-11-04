package app.algoroutine.core
import kotlin.test.*

class OrbitClockTest {
    private val day=1_800_000_000_000L - 1_800_000_000_000L % 86_400_000L
    private fun at(h:Int,m:Int=0)=day+(h*60L+m)*60_000L
    private val three=RunDefinition("r",1,"Routine","me",listOf(RoutineStep("a","A"),RoutineStep("b","B"),RoutineStep("c","C")))

    @Test fun dayItemsSitAtTheirTimesAndOutsideTheWindowAreHidden() {
        val items=listOf("doctor" to at(15),"sync" to at(17),"write" to at(17,30),"budget" to at(18,30))
        val p=OrbitClock.positions(items,at(17,2),OrbitScales.DAY).associateBy{it.id}
        assertEquals(-2.0/60,p.getValue("sync").offset!!,1e-9)
        assertEquals(28.0/60,p.getValue("write").offset!!,1e-9)
        assertTrue(p.getValue("doctor").hidden);assertNull(p.getValue("doctor").offset)
        assertTrue(p.getValue("budget").hidden);assertFalse(p.getValue("sync").hidden)
        // one minute later everything is 1/60 higher (the orbit turns like a clock)
        val q=OrbitClock.positions(items,at(17,3),OrbitScales.DAY).associateBy{it.id}
        assertEquals(p.getValue("write").offset!!-1.0/60,q.getValue("write").offset!!,1e-9)
        assertEquals(p.getValue("sync").offset!!-1.0/60,q.getValue("sync").offset!!,1e-9)
    }

    private fun engine():WorkspaceEngine {
        val e=WorkspaceEngine()
        e.execute(RunCommand("s","start","run",0,definition=three),at(14))
        val r=e.view().runs[0];e.execute(RunCommand("c1","complete","run",r.revision,"a",e.view().focusRevision),at(14,2))
        return e
    }

    @Test fun routineStepsFromRecordedEventsAndDefaultLength() {
        val e=engine()
        val s=OrbitClock.steps(e.view().runs[0],e.events(),at(14,5)).associateBy{it.id}
        assertEquals("done",s.getValue("a").role);assertEquals(at(14,2),s.getValue("a").atMillis)
        assertEquals(-3.0/15,s.getValue("a").offset!!,1e-9)
        val b=s.getValue("b");assertEquals("current",b.role);assertEquals(0.0,b.offset!!,1e-9)
        assertEquals(at(14,2),b.startMillis);assertEquals(at(14,7),b.endMillis)
        assertEquals(2.0/15,b.endOffset!!,1e-9);assertEquals(-3.0/15,b.startOffset!!,1e-9)
        val c=s.getValue("c");assertEquals("next",c.role);assertEquals(at(14,7),c.atMillis);assertEquals(2.0/15,c.offset!!,1e-9)
        // one minute later: the done step and the next step move up by 1/15; the current step stays at now
        val t=OrbitClock.steps(e.view().runs[0],e.events(),at(14,6)).associateBy{it.id}
        assertEquals(-4.0/15,t.getValue("a").offset!!,1e-9);assertEquals(0.0,t.getValue("b").offset!!,1e-9)
        assertEquals(1.0/15,t.getValue("b").endOffset!!,1e-9);assertEquals(1.0/15,t.getValue("c").offset!!,1e-9)
    }

    @Test fun overrunStepEndsAtNowAndNextStepsFollow() {
        val s=OrbitClock.steps(engine().view().runs[0],engine().events(),at(14,12)).associateBy{it.id}
        assertEquals(at(14,12),s.getValue("b").endMillis);assertEquals(at(14,12),s.getValue("c").atMillis)
        assertEquals(-10.0/15,s.getValue("a").offset!!,1e-9)
        assertTrue(OrbitClock.steps(engine().view().runs[0],engine().events(),at(14,18)).first{it.id=="a"}.hidden) // 16 min ago: off the arc
    }

    @Test fun windowIsSplitEvenlyOverRemainingSteps() {
        val e=WorkspaceEngine()
        e.execute(RunCommand("s","start","run",0,definition=three.copy(windowStartMillis=at(14),windowEndMillis=at(14,30))),at(14))
        val s=OrbitClock.steps(e.view().runs[0],e.events(),at(14,1))
        // 30 min over 3 remaining steps from 14:00 -> 10 min each
        assertEquals(listOf(at(14,1),at(14,10),at(14,20)),s.map{it.atMillis})
        assertEquals(at(14,10),s[0].endMillis);assertEquals(9.0/15,s[1].offset!!,1e-9);assertTrue(s[2].hidden) // 14:20 is past now+15
    }

    @Test fun completedStepWithoutKnownTimeSitsOneTickAboveNow() {
        val run=RunView("x",three,2,"running","c",2,0,null,listOf(StepView("a","A","completed"),StepView("b","B","completed"),StepView("c","C","pending")))
        val s=OrbitClock.steps(run,emptyList(),at(14)).associateBy{it.id}
        assertEquals(at(13,50),s.getValue("a").atMillis);assertEquals(at(13,55),s.getValue("b").atMillis)
        assertEquals(0.0,s.getValue("c").offset!!,1e-9)
    }

    @Test fun focusedDayItemSitsAtNowWithItsTimer() {
        val e=engine()
        val items=DayOrbit.items(e.view().runs,emptyList(),DayOrbit.startTimes(e.events()),at(14,5),day,day+86_400_000L)
        val d=OrbitClock.day(items,e.view().runs,e.events(),"run",at(14,5))
        assertEquals("current",d[0].role);assertEquals(0.0,d[0].offset!!,1e-9)
        assertEquals(at(14),d[0].startMillis);assertEquals(at(14,12),d[0].endMillis) // b to 14:07, c to 14:12
        assertEquals(-5.0/60,d[0].startOffset!!,1e-9);assertEquals(7.0/60,d[0].endOffset!!,1e-9)
    }
}
