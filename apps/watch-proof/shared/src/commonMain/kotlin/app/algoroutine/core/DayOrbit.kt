package app.algoroutine.core
import kotlinx.serialization.Serializable

/** One item of "My routine" (the user's whole day, the level above a routine's steps).
 *  kind: "run" = a running occurrence (its steps are the level below), "reservation" = a reservation not started yet.
 *  atMillis is the orbit sort key: the reservation/window start, else the run's recorded start, else now.
 *  position/total: the run's current step (1-based) in its effective order; 0 when unknown or for reservations.
 *  plain: a plain schedule (no steps): a reservation of kind "schedule", or a run started from one. */
@Serializable data class DayItem(
    val kind:String, val id:String, val title:String, val atMillis:Long,
    val startMillis:Long?=null, val endMillis:Long?=null,
    val position:Int=0, val total:Int=0,
    val definitionId:String, val definitionVersion:Int, val occurrenceId:String,
    val plain:Boolean=false,
)

/** Read-only ordering of today's items. Never starts, focuses or completes anything. */
object DayOrbit {
    /** First recorded start per occurrence. */
    fun startTimes(events:List<RunEvent>):Map<String,Long> {
        val out=linkedMapOf<String,Long>()
        for(e in events) if(e.kind=="start" && e.occurrenceId !in out) out[e.occurrenceId]=e.atMillis
        return out
    }

    /** Running runs (window not elapsed) + today's active reservations whose occurrence has not started.
     *  Skipped / unscheduled (any non-null status) reservations are not shown. Ordered by time, runs before reservations on ties. */
    fun items(runs:List<RunView>, reservations:List<Reservation>, startedAt:Map<String,Long>, nowMillis:Long, dayStartMillis:Long, dayEndMillis:Long):List<DayItem> {
        val started=runs.map{it.id}.toSet()
        val live=runs.filter{it.status=="running" && (it.definition.windowEndMillis==null || nowMillis<it.definition.windowEndMillis)}.map{r->
            val order=r.order.ifEmpty{r.steps.map{it.id}}
            val index=r.currentUnitId?.let{order.indexOf(it)} ?: -1
            DayItem("run",r.id,r.definition.title,r.definition.windowStartMillis ?: startedAt[r.id] ?: nowMillis,
                r.definition.windowStartMillis,r.definition.windowEndMillis,if(index>=0)index+1 else 0,order.size,
                r.definition.id,r.definition.version,r.id,plain=r.definition.steps.isEmpty())
        }
        val planned=reservations.filter{it.status==null && (it.occurrenceId==null || it.occurrenceId !in started) && it.startMillis>=dayStartMillis && it.startMillis<dayEndMillis && it.startMillis<it.endMillis}.map{x->
            DayItem("reservation",x.id,x.title,x.startMillis,x.startMillis,x.endMillis,definitionId=x.definitionId,definitionVersion=x.definitionVersion,occurrenceId=x.occurrenceId ?: "reserved-${x.id}",plain=x.kind==ReservationKind.SCHEDULE)
        }
        return (live+planned).sortedWith(compareBy<DayItem>({it.atMillis},{if(it.kind=="run")0 else 1},{it.id}))
    }
}
