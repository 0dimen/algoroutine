package app.algoroutine.core
import kotlin.test.*

class DayOrbitTest {
    private val day=1_800_000_000_000L - 1_800_000_000_000L % 86_400_000L
    private fun at(h:Int,m:Int=0)=day+(h*60L+m)*60_000L
    private val report=RunDefinition("report",1,"Start a report","me",listOf(RoutineStep("open","Open a blank document"),RoutineStep("heading","Write a working heading"),RoutineStep("points","List three key points")))
    private val rest=RunDefinition("rest",1,"Burnout reset","me",listOf(RoutineStep("phone","Put your phone face down")))
    private fun res(id:String,title:String,start:Long,end:Long,status:String?=null,occurrence:String?="reserved-$id")=Reservation(id,"d-$id",1,title,start,end,occurrence,status=status)
    /** State recorded after the rest proposal was applied (fixture prepared at 14:00). */
    private fun applied()=listOf(
        res("team-sync","Team sync",at(17),at(17,30)),
        res("doctor-call","Doctor call",at(15),at(15,15)),
        res("budget-draft","Budget draft",at(18,30),at(19,30)),
        res("deep-work-block","Deep work block",at(16),at(18),status="unscheduled"),
        res("write-report-section","Write report section",at(17,30),at(18,30)),
    )
    private fun workspace():WorkspaceEngine {
        val e=WorkspaceEngine()
        e.execute(RunCommand("s1","start","demo-report",0,definition=report),at(14))
        val r=e.view().runs[0];e.execute(RunCommand("c1","complete",r.id,r.revision,r.currentUnitId,e.view().focusRevision),at(14))
        e.execute(RunCommand("s2","start","rest-run",e.view().revision,definition=rest),at(14,5))
        return e
    }

    @Test fun appliedRestStateOrdersTheWholeDayByTime() {
        val e=workspace()
        val items=DayOrbit.items(e.view().runs,applied(),DayOrbit.startTimes(e.events()),at(17,2),day,day+86_400_000L)
        assertEquals(listOf("Start a report","Burnout reset","Doctor call","Team sync","Write report section","Budget draft"),items.map{it.title})
        assertEquals(listOf(at(14),at(14,5),at(15),at(17),at(17,30),at(18,30)),items.map{it.atMillis})
        val run=items[0];assertEquals("run",run.kind);assertEquals("demo-report",run.id);assertEquals(2,run.position);assertEquals(3,run.total);assertNull(run.startMillis)
        val sync=items[3];assertEquals("reservation",sync.kind);assertEquals(at(17),sync.startMillis);assertEquals(at(17,30),sync.endMillis);assertEquals("reserved-team-sync",sync.occurrenceId)
        assertTrue(items.none{it.title=="Deep work block"})
    }

    @Test fun hiddenAndSupersededItemsAreNotShown() {
        val e=workspace()
        val extra=applied()+listOf(
            res("skipped","Skipped one",at(19),at(19,30),status="skipped"),
            res("yesterday","Yesterday",at(9)-86_400_000L,at(10)-86_400_000L),
            res("tomorrow","Tomorrow",at(9)+86_400_000L,at(10)+86_400_000L),
            res("started","Already started",at(14),at(20),occurrence="rest-run"),
        )
        val items=DayOrbit.items(e.view().runs,extra,DayOrbit.startTimes(e.events()),at(17,2),day,day+86_400_000L)
        assertTrue(items.none{it.title in setOf("Skipped one","Yesterday","Tomorrow","Already started","Deep work block")})
        assertEquals(1,items.count{it.title=="Burnout reset"})
    }

    @Test fun timedRunSitsAtItsWindowAndUnknownStartIsNow() {
        val timed=RunView("reserved-x",report.copy(windowStartMillis=at(16),windowEndMillis=at(18)),0,"running","open",0,0,null,report.steps.map{StepView(it.id,it.title,"pending")})
        val untimed=RunView("free",rest,0,"running","phone",0,0,null,emptyList())
        val done=RunView("done",rest,1,"completed",null,1,0,"required_children",emptyList())
        val elapsed=RunView("late",report.copy(windowStartMillis=at(12),windowEndMillis=at(13)),0,"running","open",0,0,null,emptyList())
        val items=DayOrbit.items(listOf(timed,untimed,done,elapsed),emptyList(),emptyMap(),at(17),day,day+86_400_000L)
        assertEquals(listOf("reserved-x","free"),items.map{it.id})
        assertEquals(listOf(at(16),at(17)),items.map{it.atMillis})
        assertEquals(at(18),items[0].endMillis);assertEquals(1,items[0].position)
    }

    @Test fun orderingIsReadOnly() {
        val e=workspace();val before=e.view()
        DayOrbit.items(before.runs,applied(),DayOrbit.startTimes(e.events()),at(17,2),day,day+86_400_000L)
        assertEquals(before,e.view())
    }
}
