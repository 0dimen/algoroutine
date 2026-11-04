package app.algoroutine.core
import kotlinx.serialization.Serializable

/** required/movable/deadline are schedule facts (older reservations read as not required, movable, no deadline).
 *  status: null = active, "skipped" = not this time (app only), "unscheduled" = re-coordination list. history keeps earlier times. */
@Serializable data class Reservation(val id:String,val definitionId:String,val definitionVersion:Int,val title:String,val startMillis:Long,val endMillis:Long,val occurrenceId:String?=null,
    val required:Boolean=false,val movable:Boolean=true,val deadlineMillis:Long?=null,val status:String?=null,val history:List<ReservationChange> = emptyList())
@Serializable data class ReservationChange(val applyId:String,val atMillis:Long,val action:String,val source:String,val fromStartMillis:Long,val fromEndMillis:Long)
@Serializable data class ReservationSelection(val state:String,val candidates:List<Reservation>,val reason:String?=null)
class ScheduleSelector {
    fun select(all:List<Reservation>,nowMillis:Long,complete:Boolean):ReservationSelection {
        val items=all.filter{it.status==null} // skipped / unscheduled items are never the current or next reservation
        if(!complete)return ReservationSelection("unavailable",emptyList(),"INCOMPLETE_READ")
        if(items.any{it.id.isBlank()||it.startMillis>=it.endMillis} || items.map{it.id}.toSet().size!=items.size)
            return ReservationSelection("unavailable",emptyList(),"INVALID_RESERVATION")
        val active=items.filter{it.startMillis<=nowMillis&&nowMillis<it.endMillis}
        if(active.isNotEmpty())return ReservationSelection(if(active.size==1)"selected" else "conflict",active)
        val next=items.filter{nowMillis<it.startMillis}; val first=next.minOfOrNull{it.startMillis} ?: return ReservationSelection("none",emptyList())
        val tied=next.filter{it.startMillis==first}
        return ReservationSelection(if(tied.size==1)"selected" else "conflict",tied)
    }
}
