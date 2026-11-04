package app.algoroutine.core
import kotlinx.serialization.Serializable

/*
 * Rest-mode batch reschedule (2026-11-04 user decision).
 * The AI proposes; these app rules validate. Rule-based planning is both the fallback when the AI is
 * unavailable and the alternative shown next to an AI suggestion that fails validation.
 *
 * Actions: "move" (new start, same duration), "skip_this_time" (app-internal only; never cancels an
 * external booking), "keep" (no change), "later" (re-coordination list; no invented time).
 */
object RestAction { const val MOVE="move"; const val SKIP="skip_this_time"; const val KEEP="keep"; const val LATER="later"
    val all=setOf(MOVE,SKIP,KEEP,LATER) }

/** One proposed or chosen outcome for an affected reservation. newStartMillis only for move. */
@Serializable data class RestDecision(val reservationId:String,val action:String,val newStartMillis:Long?=null,val reason:String?=null,val source:String="rule")
/** Validation issue codes: UNKNOWN_ID, NOT_AFFECTED, DUPLICATE, REQUIRED_FIXED, NOT_MOVABLE, BAD_ACTION, MISSING_TIME,
 *  INSIDE_REST_WINDOW, PAST_DAY_END, PAST_DEADLINE, OVERLAP. */
@Serializable data class RestIssue(val reservationId:String,val code:String)
/** Per affected reservation: the AI suggestion (if any), whether it passed, the rule alternative and the default to apply. */
@Serializable data class RestItem(val reservation:Reservation,val ai:RestDecision?=null,val aiIssues:List<String> = emptyList(),
                                  val alternative:RestDecision,val proposed:RestDecision,val allowed:List<String>)
@Serializable data class RestProposal(val occurrenceId:String,val restStartMillis:Long,val restEndMillis:Long,val dayEndMillis:Long,
                                      val expectedRevision:String,val source:String,val items:List<RestItem>,val fixed:List<Reservation>)
@Serializable data class RestApplyResult(val accepted:Boolean,val reason:String,val issues:List<RestIssue> = emptyList(),val reservations:List<Reservation> = emptyList())

class RestRescheduler {
    fun active(r:Reservation)=r.status==null
    /** Unstarted, active reservations overlapping [restStart,restEnd), in start order. Started occurrences are never touched. */
    fun affected(items:List<Reservation>,started:Set<String>,restStart:Long,restEnd:Long)=
        items.filter{active(it) && !(it.occurrenceId!=null && it.occurrenceId in started) && it.startMillis<restEnd && it.endMillis>restStart}
            .sortedWith(compareBy({it.startMillis},{it.id}))
    fun allowed(r:Reservation)=when{ r.required->listOf(RestAction.KEEP); !r.movable->listOf(RestAction.KEEP,RestAction.SKIP)
        else->listOf(RestAction.MOVE,RestAction.SKIP,RestAction.KEEP,RestAction.LATER) }

    /**
     * Checks one decision against the reservations that stay where they are (occupied intervals).
     * Returns issue codes; empty means the decision is possible.
     */
    fun check(r:Reservation,d:RestDecision,occupied:List<Pair<Long,Long>>,restEnd:Long,dayEnd:Long):List<String> {
        if(d.action !in RestAction.all) return listOf("BAD_ACTION")
        if(r.required && d.action!=RestAction.KEEP) return listOf("REQUIRED_FIXED")
        if(!r.movable && d.action !in setOf(RestAction.KEEP,RestAction.SKIP)) return listOf("NOT_MOVABLE")
        if(d.action!=RestAction.MOVE) return if(d.newStartMillis!=null) listOf("BAD_ACTION") else emptyList()
        val start=d.newStartMillis?:return listOf("MISSING_TIME");val end=start+(r.endMillis-r.startMillis)
        val out=mutableListOf<String>()
        if(start<restEnd) out+="INSIDE_REST_WINDOW"
        if(end>dayEnd) out+="PAST_DAY_END"
        if(r.deadlineMillis!=null && end>r.deadlineMillis) out+="PAST_DEADLINE"
        if(occupied.any{(a,b)->a<end && b>start}) out+="OVERLAP"
        return out
    }
    /** Earliest same-length slot at/after the rest end that fits the day end and deadline; otherwise skip this time. */
    fun alternative(r:Reservation,occupied:List<Pair<Long,Long>>,restEnd:Long,dayEnd:Long):RestDecision {
        if(r.required) return RestDecision(r.id,RestAction.KEEP,reason="REQUIRED")
        if(!r.movable) return RestDecision(r.id,RestAction.KEEP,reason="NOT_MOVABLE")
        val duration=r.endMillis-r.startMillis;var start=restEnd;val limit=minOf(dayEnd,r.deadlineMillis?:Long.MAX_VALUE)
        while(true){val blocking=occupied.filter{(a,b)->a<start+duration && b>start};if(blocking.isEmpty())break;start=blocking.maxOf{it.second}}
        return if(start+duration<=limit) RestDecision(r.id,RestAction.MOVE,start,reason="EARLIEST_FREE")
        else RestDecision(r.id,RestAction.SKIP,reason=if(r.deadlineMillis!=null && r.deadlineMillis<dayEnd) "DOES_NOT_FIT_DEADLINE" else "DOES_NOT_FIT_DAY_END")
    }
    private fun interval(r:Reservation,d:RestDecision):Pair<Long,Long>? = when(d.action){
        RestAction.KEEP->r.startMillis to r.endMillis
        RestAction.MOVE->d.newStartMillis!! to d.newStartMillis+(r.endMillis-r.startMillis)
        else->null }

    /**
     * Builds the batch proposal. AI suggestions are validated in reservation order against everything already placed;
     * a failing or missing suggestion falls back to the rule alternative computed against the same placements.
     * Suggestions for unknown or unaffected ids are ignored (reported via [rejectedSuggestions]).
     */
    fun propose(items:List<Reservation>,started:Set<String>,occurrenceId:String,restStart:Long,restEnd:Long,dayEnd:Long,suggestions:List<RestDecision>?):RestProposal {
        require(restStart<restEnd)
        require(items.map{it.id}.toSet().size==items.size)
        val affected=affected(items,started,restStart,restEnd);val ids=affected.map{it.id}.toSet()
        val fixed=items.filter{active(it) && it.id !in ids}
        val occupied=fixed.map{it.startMillis to it.endMillis}.toMutableList()
        val byId=suggestions?.groupBy{it.reservationId}.orEmpty()
        val ai=affected.associate{r->r.id to byId[r.id]?.let{if(it.size==1)it.single().copy(source="ai") else null}}
        val aiIssues=mutableMapOf<String,List<String>>();val chosen=mutableMapOf<String,RestDecision>()
        // Pass 1: decisions that stay in place or leave the timeline (keep/skip/later) settle first,
        // so later moves are checked against every interval that remains.
        for(r in affected){
            val a=ai[r.id]
            val codes=a?.let{check(r,it,emptyList(),restEnd,dayEnd)}
            if(r.required||!r.movable){ // never moves, so it settles here either way
                if(codes!=null)aiIssues[r.id]=codes
                chosen[r.id]=if(a!=null && codes!!.isEmpty()) a else alternative(r,occupied,restEnd,dayEnd)
            } else if(a!=null && a.action!=RestAction.MOVE && codes!!.isEmpty()) chosen[r.id]=a
            chosen[r.id]?.let{d->interval(r,d)?.let{occupied+=it}}
        }
        // Pass 2: moves (AI first, otherwise the rule alternative) in original start order.
        for(r in affected.filter{it.id !in chosen}){
            val a=ai[r.id]
            if(a!=null){val codes=check(r,a,occupied,restEnd,dayEnd);aiIssues[r.id]=codes;if(codes.isEmpty())chosen[r.id]=a}
            if(r.id !in chosen) chosen[r.id]=alternative(r,occupied,restEnd,dayEnd)
            interval(r,chosen.getValue(r.id))?.let{occupied+=it}
        }
        val result=affected.map{r->
            val issues=when{suggestions==null->emptyList();ai[r.id]==null->listOf(if((byId[r.id]?.size?:0)>1)"DUPLICATE" else "MISSING");else->aiIssues[r.id].orEmpty()}
            val placedWithoutMe=occupied.toMutableList().also{l->interval(r,chosen.getValue(r.id))?.let{l.remove(it)}}
            RestItem(r,ai[r.id],issues,if(issues.isEmpty()&&ai[r.id]!=null) alternative(r,placedWithoutMe,restEnd,dayEnd) else chosen.getValue(r.id),chosen.getValue(r.id),allowed(r))
        }
        val source=if(suggestions==null) "rule" else "ai"
        return RestProposal(occurrenceId,restStart,restEnd,dayEnd,revision(items),source,result,fixed)
    }
    fun rejectedSuggestions(items:List<Reservation>,started:Set<String>,restStart:Long,restEnd:Long,suggestions:List<RestDecision>):List<RestIssue> {
        val ids=affected(items,started,restStart,restEnd).map{it.id}.toSet();val known=items.map{it.id}.toSet()
        return suggestions.filter{it.reservationId !in ids}.map{RestIssue(it.reservationId,if(it.reservationId in known)"NOT_AFFECTED" else "UNKNOWN_ID")}
    }

    /**
     * Validates the final chosen decisions as one set. Every affected reservation needs exactly one decision.
     * Moves must not overlap fixed reservations, kept items, or each other.
     */
    fun validate(items:List<Reservation>,started:Set<String>,restStart:Long,restEnd:Long,dayEnd:Long,decisions:List<RestDecision>):List<RestIssue> {
        val affected=affected(items,started,restStart,restEnd);val ids=affected.map{it.id}.toSet();val known=items.map{it.id}.toSet()
        val issues=mutableListOf<RestIssue>()
        decisions.groupBy{it.reservationId}.forEach{(id,list)->
            if(id !in known) issues+=RestIssue(id,"UNKNOWN_ID") else if(id !in ids) issues+=RestIssue(id,"NOT_AFFECTED")
            if(list.size>1) issues+=RestIssue(id,"DUPLICATE")}
        affected.filter{r->decisions.none{it.reservationId==r.id}}.forEach{issues+=RestIssue(it.id,"MISSING")}
        if(issues.isNotEmpty()) return issues
        val byId=decisions.associateBy{it.reservationId}
        val fixed=items.filter{active(it) && it.id !in ids}.map{it.id to (it.startMillis to it.endMillis)}
        val placed=affected.mapNotNull{r->val d=byId.getValue(r.id);if(d.action in RestAction.all && (d.action!=RestAction.MOVE||d.newStartMillis!=null)) interval(r,d)?.let{r.id to it} else null}
        for(r in affected){
            val d=byId.getValue(r.id)
            val others=(fixed+placed).filter{it.first!=r.id}.map{it.second}
            // Keeping an item never conflicts by itself: the original schedule already had that interval.
            val codes=check(r,d,if(d.action==RestAction.MOVE) others else emptyList(),restEnd,dayEnd)
            codes.forEach{issues+=RestIssue(r.id,it)}
        }
        return issues
    }

    /** Applies validated decisions. Moves keep id/occurrence; skip/later only mark the item. Original times go to history. */
    fun apply(items:List<Reservation>,decisions:List<RestDecision>,applyId:String,atMillis:Long):List<Reservation> {
        val byId=decisions.associateBy{it.reservationId}
        return items.map{r->val d=byId[r.id]?:return@map r
            val entry=ReservationChange(applyId,atMillis,d.action,d.source,r.startMillis,r.endMillis)
            when(d.action){
                RestAction.MOVE->{val n=d.newStartMillis!!;r.copy(startMillis=n,endMillis=n+(r.endMillis-r.startMillis),history=r.history+entry)}
                RestAction.SKIP->r.copy(status="skipped",history=r.history+entry)
                RestAction.LATER->r.copy(status="unscheduled",history=r.history+entry)
                else->r
            }}
    }
    /** Stable FNV-1a fingerprint of the full reservation list (optimistic-concurrency revision). */
    fun revision(items:List<Reservation>):String {
        var h=-0x340d631b7bdddcdbL
        for(c in items.joinToString("\n"){listOf(it.id,it.definitionId,it.definitionVersion,it.title,it.startMillis,it.endMillis,it.occurrenceId,it.required,it.movable,it.deadlineMillis,it.status,it.history.size).joinToString("\u0001")}){h=(h xor c.code.toLong())*0x100000001b3L}
        return h.toULong().toString(16)
    }
}
