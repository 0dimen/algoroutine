package app.algoroutine.core
import kotlin.test.*

/** Plain schedule (2026-11-04 user decision): a timed plan with no steps, e.g. "Team sync" 17:00–17:30. */
class PlainScheduleTest {
    private val day=1_800_000_000_000L - 1_800_000_000_000L % 86_400_000L
    private fun at(h:Int,m:Int=0)=day+(h*60L+m)*60_000L
    private fun plain(id:String,title:String,start:Long,end:Long,required:Boolean=false,movable:Boolean=true,deadline:Long?=null)=
        Reservation(id,ReservationKind.PLAIN_SCHEDULE_ID,1,title,start,end,"reserved-$id",required,movable,deadline,kind=ReservationKind.SCHEDULE)
    private val sync=plain("team-sync","Team sync",at(17),at(17,30))

    @Test fun plainScheduleSitsInTheDayByTimeAndIsMarkedPlain() {
        val routine=Reservation("burnout","burnout-def",1,"Burnout reset",at(20),at(21),"reserved-burnout")
        val early=Reservation("doctor","doctor-def",1,"Doctor call",at(15),at(15,15),"reserved-doctor")
        val items=DayOrbit.items(emptyList(),listOf(routine,sync,early),emptyMap(),at(14),day,day+86_400_000L)
        assertEquals(listOf("Doctor call","Team sync","Burnout reset"),items.map{it.title})
        assertEquals(listOf(false,true,false),items.map{it.plain})
        assertEquals(ReservationKind.ROUTINE,routine.kind)
        assertEquals(at(17) to at(17,30),items[1].startMillis to items[1].endMillis)
    }

    @Test fun plainScheduleNeverStartsByItselfThenStartAndDone() {
        val e=WorkspaceEngine();val d=ReservationKind.plainDefinition(sync)
        assertEquals(emptyList(),d.steps);assertEquals(at(17),d.windowStartMillis)
        // Time passing alone never creates a run.
        assertTrue(DayOrbit.items(e.view().runs,listOf(sync),emptyMap(),at(17,5),day,day+86_400_000L).single().kind=="reservation")
        assertEquals("EARLY_START",e.execute(RunCommand("early","start","reserved-team-sync",0,definition=d),at(16,59)).reason)
        val started=e.execute(RunCommand("go","start","reserved-team-sync",e.view().revision,definition=d),at(17))
        assertTrue(started.accepted)
        val run=started.view.runs.single();assertEquals("running",run.status);assertNull(run.currentUnitId);assertEquals(0,run.steps.size)
        val item=DayOrbit.items(started.view.runs,listOf(sync),DayOrbit.startTimes(e.events()),at(17,1),day,day+86_400_000L).single()
        assertEquals("run",item.kind);assertTrue(item.plain);assertEquals(0,item.total)
        // A step command has no target; Done (completeParent) completes it.
        assertEquals("WRONG_TARGET",e.execute(RunCommand("step","complete",run.id,run.revision,null,e.view().focusRevision),at(17,2)).reason)
        val done=e.execute(RunCommand("done","completeParent",run.id,run.revision,null,e.view().focusRevision),at(17,2))
        assertTrue(done.accepted);assertEquals("completed",done.view.runs.single().status);assertEquals("direct_parent",done.view.runs.single().evidence)
        assertTrue(DayOrbit.items(done.view.runs,listOf(sync),DayOrbit.startTimes(e.events()),at(17,3),day,day+86_400_000L).isEmpty())
    }

    @Test fun zeroStepsWithoutAWindowIsStillInvalid() {
        val bare=RunDefinition("schedule",1,"Untimed","me",emptyList())
        assertEquals("INVALID_DEFINITION",WorkspaceEngine().execute(RunCommand("s","start","x",0,definition=bare),at(9)).reason)
    }

    @Test fun plainScheduleThatReachesItsEndElapses() {
        val e=WorkspaceEngine();e.execute(RunCommand("go","start","reserved-team-sync",0,definition=ReservationKind.plainDefinition(sync)),at(17))
        val r=e.execute(RunCommand("system:elapsed:reserved-team-sync","expire","reserved-team-sync",0),at(17,30))
        assertTrue(r.accepted);assertEquals("elapsed",r.view.runs.single().status)
    }

    @Test fun restProposalTreatsPlainSchedulesLikeOtherReservations() {
        val p=RestRescheduler()
        val items=listOf(plain("sync","Team sync",at(14,30),at(15)),plain("doctor","Doctor call",at(15),at(15,15),required=true),
            plain("standup","Fixed standup",at(16),at(16,15),movable=false),plain("late","Late plan",at(18),at(18,30)))
        val x=p.propose(items,emptySet(),"rest",at(14),at(17),at(21),null);val d=x.items.associate{it.reservation.id to it.proposed}
        assertEquals(listOf("sync","doctor","standup"),x.items.map{it.reservation.id});assertEquals(listOf("late"),x.fixed.map{it.id})
        assertEquals(RestAction.MOVE to at(17),d.getValue("sync").action to d.getValue("sync").newStartMillis)
        assertEquals(RestAction.KEEP,d.getValue("doctor").action);assertEquals(listOf(RestAction.KEEP),x.items.single{it.reservation.id=="doctor"}.allowed)
        assertEquals(RestAction.KEEP,d.getValue("standup").action)
        // An AI suggestion to move the required plain schedule is rejected; the valid one is kept as is.
        val ai=p.propose(items,emptySet(),"rest",at(14),at(17),at(21),listOf(RestDecision("sync",RestAction.MOVE,at(19)),RestDecision("doctor",RestAction.MOVE,at(19,30)),RestDecision("standup",RestAction.KEEP)))
        val byId=ai.items.associateBy{it.reservation.id}
        assertEquals(at(19),byId.getValue("sync").proposed.newStartMillis);assertEquals("ai",byId.getValue("sync").proposed.source)
        assertEquals(listOf("REQUIRED_FIXED"),byId.getValue("doctor").aiIssues);assertEquals(RestAction.KEEP,byId.getValue("doctor").proposed.action)
        val after=p.apply(items,ai.items.map{it.proposed},"apply",at(14,1)).associateBy{it.id}
        assertEquals(at(19) to at(19,30),after.getValue("sync").let{it.startMillis to it.endMillis});assertEquals(ReservationKind.SCHEDULE,after.getValue("sync").kind)
        assertEquals(at(15),after.getValue("doctor").startMillis)
        assertTrue(p.validate(items,emptySet(),at(14),at(17),at(21),ai.items.map{it.proposed}).isEmpty())
    }
}
