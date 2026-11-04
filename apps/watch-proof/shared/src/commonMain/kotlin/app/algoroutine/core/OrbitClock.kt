package app.algoroutine.core
import kotlinx.serialization.Serializable

/** One node on the clock orbit (user decision 2026-11-04: the whole orbit is one clock).
 *  atMillis = where the node sits on the clock; the "current" node sits at now.
 *  startMillis/endMillis = the item's (expected) time span, for the visual timer: thin dark arc start..now (elapsed),
 *  thick arc now..end (remaining). offset/endOffset/startOffset = position on the visible arc for nowMillis
 *  (-1 top end = past, 0 = now, 1 bottom end = future); null = outside the window (hidden: not drawn as a node).
 *  role: "done" | "current" | "next" (steps), "item" | "current" (day). */
@Serializable data class OrbitSlot(
    val id:String, val role:String, val atMillis:Long, val startMillis:Long?=null, val endMillis:Long?=null,
    val offset:Double?=null, val startOffset:Double?=null, val endOffset:Double?=null, val hidden:Boolean=true,
)

/** Pure clock math. Clients re-derive offsets with their own (server-offset) now every minute:
 *  offset = (atMillis - now) / halfWindow, so everything slides up as time passes. */
object OrbitClock {
    /** Unclamped position on the arc (-1..1 is visible). */
    fun offset(scale:OrbitScale, atMillis:Long, nowMillis:Long):Double = (atMillis-nowMillis).toDouble()/scale.halfWindowMillis
    private fun visible(o:Double)= o>=-1.0 && o<=1.0
    private fun clamp(o:Double)= o.coerceIn(-1.0,1.0)

    /** Positions items (id to time) on the arc; outside the window = hidden, offset null. */
    fun positions(items:List<Pair<String,Long>>, nowMillis:Long, scale:OrbitScale):List<OrbitSlot> =
        items.map{(id,at)->place(OrbitSlot(id,"item",at),nowMillis,scale)}

    /** Fills offsets for now. Timer offsets (start/end) are clamped to the window so arcs stop at its ends. */
    fun place(s:OrbitSlot, nowMillis:Long, scale:OrbitScale):OrbitSlot {
        val o=offset(scale,s.atMillis,nowMillis)
        return s.copy(offset=if(visible(o))o else null,hidden=!visible(o),
            startOffset=s.startMillis?.let{clamp(offset(scale,it,nowMillis))},endOffset=s.endMillis?.let{clamp(offset(scale,it,nowMillis))})
    }

    /** Step times of one run, from the recorded events only (no invented history):
     *  - done (completed / skipped): at the time of its complete/skip event; unknown -> just above now, one tick apart.
     *  - current: started when the queue head last changed (start / complete / skip / defer event of this run), sits at now;
     *    expected end = start + step length (never before now).
     *  - next: one after another from the current step's expected end.
     *  Step length: the run's time window split evenly over the remaining steps (from the current step's start),
     *  else OrbitScales.DEFAULT_STEP_MINUTES. */
    fun steps(run:RunView, events:List<RunEvent>, nowMillis:Long, scale:OrbitScale=OrbitScales.ROUTINE, defaultStepMinutes:Int=OrbitScales.DEFAULT_STEP_MINUTES):List<OrbitSlot> {
        val order=run.order.ifEmpty{run.steps.map{it.id}}
        val status=run.steps.associate{it.id to it.status}
        val mine=events.filter{it.occurrenceId==run.id && it.atMillis<=nowMillis}
        val finishedAt=mine.filter{it.kind=="complete"||it.kind=="skip"}.mapNotNull{e->e.unitId?.let{it to e.atMillis}}.toMap()
        val currentId=run.currentUnitId
        val currentStart=(mine.filter{it.kind in setOf("start","complete","skip","defer")}.maxOfOrNull{it.atMillis} ?: nowMillis).coerceAtMost(nowMillis)
        val remaining=order.count{status[it]=="pending"}.coerceAtLeast(1)
        val end=run.definition.windowEndMillis
        val length=if(end!=null && end>currentStart) ((end-currentStart)/remaining).coerceAtLeast(60_000L) else defaultStepMinutes*60_000L
        val out=mutableListOf<OrbitSlot>()
        val done=order.filter{status[it]=="completed"||status[it]=="skipped"}
        val unknown=done.filter{it !in finishedAt}
        for(id in order) {
            when {
                id in done -> {
                    val at=finishedAt[id] ?: (nowMillis-(unknown.size-unknown.indexOf(id))*scale.tickMinutes*60_000L)
                    out+=OrbitSlot(id,"done",at)
                }
                id==currentId -> out+=OrbitSlot(id,"current",nowMillis,currentStart,maxOf(nowMillis,currentStart+length))
            }
        }
        var next=out.firstOrNull{it.role=="current"}?.endMillis ?: nowMillis
        for(id in order) if(id!=currentId && status[id]=="pending") { out+=OrbitSlot(id,"next",next,next,next+length); next+=length }
        val rank=order.withIndex().associate{it.value to it.index}
        return out.sortedBy{rank[it.id]}.map{place(it,nowMillis,scale)}
    }

    /** "My routine" items on the day clock: reservations at their start, running routines at their start,
     *  the focused running item (focusId) at now with its window end, else its expected end
     *  (last step's expected end from steps(), at least now). */
    fun day(items:List<DayItem>, runs:List<RunView>, events:List<RunEvent>, focusId:String?, nowMillis:Long, scale:OrbitScale=OrbitScales.DAY):List<OrbitSlot> =
        items.map{x->
            if(x.kind=="run" && x.id==focusId) {
                val run=runs.firstOrNull{it.id==x.id}
                val expected=x.endMillis ?: run?.let{steps(it,events,nowMillis).mapNotNull{s->s.endMillis}.maxOrNull()} ?: nowMillis
                place(OrbitSlot(x.id,"current",nowMillis,x.startMillis ?: x.atMillis,maxOf(nowMillis,expected)),nowMillis,scale)
            } else place(OrbitSlot(x.id,"item",x.atMillis,x.startMillis,x.endMillis),nowMillis,scale)
        }
}
