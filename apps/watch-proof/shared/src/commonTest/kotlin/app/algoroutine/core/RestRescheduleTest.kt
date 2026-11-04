package app.algoroutine.core
import kotlin.test.*

/** Oracle from HANDOFF-AI-RESCHEDULE (2026-11-04): now 14:00, rest 180 min → 14:00–17:00, day end 21:00. Pure millis, no Meta. */
class RestRescheduleTest {
 private val m=60_000L
 private fun at(h:Int,min:Int=0)=(h*60+min)*m
 private fun r(id:String,title:String,a:Long,b:Long,required:Boolean=false,movable:Boolean=true,deadline:Long?=null)=Reservation(id,"def-$id",1,title,a,b,"reserved-$id",required,movable,deadline)
 private val items=listOf(r("team","Team sync",at(14,30),at(15)),r("budget","Budget draft",at(15,30),at(16,30),deadline=at(23,59)),
  r("deep","Deep work block",at(16),at(18)),r("report","Write report section",at(17,30),at(18,30)),r("doctor","Doctor call",at(15),at(15,15),required=true))
 private val p=RestRescheduler()
 private fun propose(s:List<RestDecision>?,list:List<Reservation> =items,started:Set<String> =emptySet())=p.propose(list,started,"rest",at(14),at(17),at(21),s)
 private fun move(id:String,h:Int,min:Int=0)=RestDecision(id,RestAction.MOVE,at(h,min),"ai reason")
 private fun act(id:String,a:String)=RestDecision(id,a,reason="ai reason")
 private fun proposed(x:RestProposal)=x.items.associate{it.reservation.id to it.proposed}

 @Test fun ruleAlternativeOracle(){
  val x=propose(null);val d=proposed(x)
  assertEquals("rule",x.source);assertEquals(listOf("team","doctor","budget","deep"),x.items.map{it.reservation.id})
  assertEquals(RestAction.KEEP,d.getValue("doctor").action)
  assertEquals(RestAction.MOVE to at(17),d.getValue("team").action to d.getValue("team").newStartMillis)
  assertEquals(RestAction.MOVE to at(18,30),d.getValue("budget").action to d.getValue("budget").newStartMillis)
  assertEquals(RestAction.SKIP,d.getValue("deep").action);assertEquals("DOES_NOT_FIT_DAY_END",d.getValue("deep").reason)
  assertFalse("report" in d);assertEquals(listOf("report"),x.fixed.map{it.id})
  assertEquals(listOf(RestAction.KEEP),x.items.single{it.reservation.id=="doctor"}.allowed)
 }
 @Test fun validAiSuggestionsAreShownAsIs(){
  val ai=listOf(move("team",19),act("doctor",RestAction.KEEP),move("budget",19,30),act("deep",RestAction.LATER))
  val x=propose(ai)
  assertEquals("ai",x.source);assertTrue(x.items.all{it.aiIssues.isEmpty()})
  assertEquals(ai.map{it.copy(source="ai")}.associateBy{it.reservationId},proposed(x))
 }
 @Test fun impossibleAiSuggestionsNeedCheckAndAreNeverProposed(){
  val ai=listOf(move("team",20,45),move("budget",17),move("deep",15),act("doctor",RestAction.SKIP),move("report",19),move("ghost",19))
  val x=propose(ai);val byId=x.items.associateBy{it.reservation.id}
  assertEquals(listOf("PAST_DAY_END"),byId.getValue("team").aiIssues)
  assertEquals(listOf("OVERLAP"),byId.getValue("budget").aiIssues)
  assertEquals(listOf("INSIDE_REST_WINDOW","OVERLAP"),byId.getValue("deep").aiIssues)
  assertEquals(listOf("REQUIRED_FIXED"),byId.getValue("doctor").aiIssues)
  // The applied default is the rule alternative, never the failing suggestion.
  x.items.forEach{assertEquals("rule",it.proposed.source);assertEquals(it.alternative,it.proposed)}
  assertEquals(at(17),byId.getValue("team").proposed.newStartMillis);assertEquals(at(18,30),byId.getValue("budget").proposed.newStartMillis)
  assertEquals(RestAction.SKIP,byId.getValue("deep").proposed.action);assertEquals(RestAction.KEEP,byId.getValue("doctor").proposed.action)
  assertEquals(listOf(RestIssue("report","NOT_AFFECTED"),RestIssue("ghost","UNKNOWN_ID")),p.rejectedSuggestions(items,emptySet(),at(14),at(17),ai))
  assertTrue(p.validate(items,emptySet(),at(14),at(17),at(21),x.items.map{it.proposed}).isEmpty())
 }
 @Test fun mixedAiPlanStaysConsistent(){
  // AI keeps Deep work (16:00–18:00): an AI move of Team sync to 17:00 must then fail, and the rule fallback avoids it.
  val x=propose(listOf(move("team",17),act("deep",RestAction.KEEP),move("budget",18,30),act("doctor",RestAction.KEEP)))
  val byId=x.items.associateBy{it.reservation.id}
  assertEquals(listOf("OVERLAP"),byId.getValue("team").aiIssues)
  assertEquals(at(18,30),byId.getValue("team").proposed.newStartMillis)
  assertEquals(listOf("OVERLAP"),byId.getValue("budget").aiIssues);assertEquals(at(19),byId.getValue("budget").proposed.newStartMillis)
  assertTrue(p.validate(items,emptySet(),at(14),at(17),at(21),x.items.map{it.proposed}).isEmpty())
 }
 @Test fun applyDefaultsThenOneKeepOverride(){
  val x=propose(null);val defaults=x.items.map{it.proposed}
  val after=p.apply(items,defaults,"apply-1",at(14,5)).associateBy{it.id}
  assertEquals(at(17) to at(17,30),after.getValue("team").let{it.startMillis to it.endMillis})
  assertEquals(at(18,30) to at(19,30),after.getValue("budget").let{it.startMillis to it.endMillis})
  assertEquals("skipped",after.getValue("deep").status);assertEquals(at(16) to at(18),after.getValue("deep").let{it.startMillis to it.endMillis})
  assertEquals(items.single{it.id=="doctor"},after.getValue("doctor"));assertEquals(items.single{it.id=="report"},after.getValue("report"))
  assertEquals(listOf(ReservationChange("apply-1",at(14,5),RestAction.MOVE,"rule",at(14,30),at(15))),after.getValue("team").history)
  val keepTeam=defaults.map{if(it.reservationId=="team")RestDecision("team",RestAction.KEEP,source="user") else it}
  assertTrue(p.validate(items,emptySet(),at(14),at(17),at(21),keepTeam).isEmpty())
  val kept=p.apply(items,keepTeam,"apply-2",at(14,5)).associateBy{it.id}
  assertEquals(items.single{it.id=="team"},kept.getValue("team"));assertEquals(at(18,30),kept.getValue("budget").startMillis)
 }
 @Test fun validatorRefusesImpossibleChoices(){
  val d=propose(null).items.map{it.proposed}
  fun with(x:RestDecision)=p.validate(items,emptySet(),at(14),at(17),at(21),d.map{if(it.reservationId==x.reservationId)x else it})
  assertEquals(listOf(RestIssue("team","OVERLAP")),with(RestDecision("deep",RestAction.KEEP,source="user")))
  assertEquals(listOf(RestIssue("doctor","REQUIRED_FIXED")),with(RestDecision("doctor",RestAction.MOVE,at(19,30))))
  assertEquals(listOf(RestIssue("team","PAST_DAY_END")),with(RestDecision("team",RestAction.MOVE,at(20,45))))
  assertEquals(listOf(RestIssue("team","INSIDE_REST_WINDOW")),with(RestDecision("team",RestAction.MOVE,at(16))))
  assertEquals(listOf(RestIssue("team","MISSING_TIME")),with(RestDecision("team",RestAction.MOVE)))
  assertEquals(listOf(RestIssue("team","OVERLAP"),RestIssue("budget","OVERLAP")),with(RestDecision("team",RestAction.MOVE,at(18,30))))
  assertTrue(with(RestDecision("team",RestAction.LATER,source="user")).isEmpty())
  assertEquals(listOf(RestIssue("report","NOT_AFFECTED")),p.validate(items,emptySet(),at(14),at(17),at(21),d+RestDecision("report",RestAction.KEEP)))
  assertEquals(listOf(RestIssue("x","UNKNOWN_ID")),p.validate(items,emptySet(),at(14),at(17),at(21),d+RestDecision("x",RestAction.KEEP)))
  assertEquals(listOf(RestIssue("team","DUPLICATE")),p.validate(items,emptySet(),at(14),at(17),at(21),d+d.first()))
  assertEquals(listOf(RestIssue("team","MISSING")),p.validate(items,emptySet(),at(14),at(17),at(21),d.drop(1)))
 }
 @Test fun deadlineAndNotMovable(){
  val list=items.map{when(it.id){"budget"->it.copy(deadlineMillis=at(18));"team"->it.copy(movable=false);else->it}}
  val x=propose(listOf(move("budget",18,30),act("team",RestAction.SKIP),act("doctor",RestAction.KEEP),act("deep",RestAction.SKIP)),list)
  val byId=x.items.associateBy{it.reservation.id}
  assertEquals(listOf("PAST_DEADLINE"),byId.getValue("budget").aiIssues)
  assertEquals(RestAction.SKIP to "DOES_NOT_FIT_DEADLINE",byId.getValue("budget").proposed.let{it.action to it.reason})
  assertEquals(listOf(RestAction.KEEP,RestAction.SKIP),byId.getValue("team").allowed)
  assertEquals(RestAction.SKIP,byId.getValue("team").proposed.action) // valid AI choice for a non-movable item
  assertEquals(RestAction.KEEP,propose(null,list).items.single{it.reservation.id=="team"}.proposed.action)
  assertEquals(listOf("NOT_MOVABLE"),propose(listOf(move("team",19)),list).items.single{it.reservation.id=="team"}.aiIssues)
 }
 @Test fun startedOccurrenceIsUntouchedButBlocks(){
  val x=propose(null,started=setOf("reserved-team"))
  assertFalse(x.items.any{it.reservation.id=="team"});assertTrue(x.fixed.any{it.id=="team"})
  assertEquals(at(18,30),proposed(x).getValue("budget").newStartMillis)
 }
 @Test fun skippedAndUnscheduledAreNotSelectedOrReplanned(){
  val after=p.apply(items,propose(null).items.map{if(it.reservation.id=="team")RestDecision("team",RestAction.LATER,source="user") else it.proposed},"a",at(14))
  assertEquals("unscheduled",after.single{it.id=="team"}.status)
  val sel=ScheduleSelector().select(after,at(16,10),true)
  assertTrue(sel.candidates.none{it.status!=null})
  assertEquals(listOf("doctor"),p.propose(after,emptySet(),"rest2",at(15),at(16),at(21),null).items.map{it.reservation.id})
  assertNotEquals(p.revision(items),p.revision(after))
 }
 @Test fun oldReservationJsonReadsAsDefaults(){
  val old=kotlinx.serialization.json.Json{ignoreUnknownKeys=true}.decodeFromString<List<Reservation>>("""[{"id":"x","definitionId":"d","definitionVersion":1,"title":"Old","startMillis":1,"endMillis":2,"occurrenceId":"reserved-x"}]""").single()
  assertEquals(Triple(false,true,null),Triple(old.required,old.movable,old.deadlineMillis));assertNull(old.status);assertTrue(old.history.isEmpty())
 }
 @Test fun previewIsPureAndDeterministic(){val copy=items.toList();assertEquals(propose(null),propose(null));assertEquals(copy,items)}
}
