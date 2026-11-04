package app.algoroutine.core
import kotlinx.serialization.Serializable

/** Time scale of one orbit depth, like a visual timer: the visible arc covers [now - window/2, now + window/2],
 *  "now" is the fixed orange planet, and tick marks sit on real clock times (every tickMinutes), so they slide
 *  past the planet minute by minute and the orbit seems to turn.
 *  depth: "day" = My routine (the whole day), "routine" = a routine's steps, "step" = a step's sub-steps.
 *  Phone (web, via the server context), Apple Watch and Wear OS all read these values from here only. */
@Serializable data class OrbitScale(val depth:String, val windowMinutes:Int, val tickMinutes:Int, val labelEveryMinutes:Int) {
    val halfWindowMillis:Long get() = windowMinutes*60_000L/2
}

/** One tick on the visible arc. offset in [-1, 1]: -1 = window start (top end of the arc), 0 = now, 1 = window end. */
@Serializable data class OrbitTick(val atMillis:Long, val offset:Double, val label:Boolean)

object OrbitScales {
    val DAY = OrbitScale("day", windowMinutes=120, tickMinutes=10, labelEveryMinutes=60)
    val ROUTINE = OrbitScale("routine", windowMinutes=30, tickMinutes=5, labelEveryMinutes=15)
    val STEP = OrbitScale("step", windowMinutes=10, tickMinutes=1, labelEveryMinutes=5)
    val all:List<OrbitScale> = listOf(DAY, ROUTINE, STEP)
    /** Planned length of one step when the routine has no time window (OrbitClock.steps). */
    const val DEFAULT_STEP_MINUTES = 5

    fun forDepth(depth:String):OrbitScale = all.firstOrNull{it.depth==depth} ?: DAY

    /** Position of a time on the arc (-1..1), or null when it is outside the visible window. */
    fun offset(scale:OrbitScale, atMillis:Long, nowMillis:Long):Double? {
        val o=(atMillis-nowMillis).toDouble()/scale.halfWindowMillis
        return if(o < -1.0 || o > 1.0) null else o
    }

    /** Ticks on wall-clock multiples of tickMinutes (in local time: zoneOffsetMillis = local - UTC) inside the window.
     *  label = the tick is on a multiple of labelEveryMinutes. Ticks move only when now crosses a minute,
     *  so callers re-draw once a minute (or when the server clock jumps, e.g. the demo clock). */
    fun ticks(scale:OrbitScale, nowMillis:Long, zoneOffsetMillis:Long=0L):List<OrbitTick> {
        val step=scale.tickMinutes*60_000L
        val localNow=nowMillis+zoneOffsetMillis
        val first=floorDiv(localNow-scale.halfWindowMillis+step-1, step)*step
        val out=mutableListOf<OrbitTick>()
        var local=first
        while(local<=localNow+scale.halfWindowMillis) {
            val at=local-zoneOffsetMillis
            val minuteOfDay=floorMod(local/60_000L, 24L*60)
            out+=OrbitTick(at,(at-nowMillis).toDouble()/scale.halfWindowMillis, minuteOfDay%scale.labelEveryMinutes==0L)
            local+=step
        }
        return out
    }

    private fun floorDiv(a:Long, b:Long):Long { val q=a/b; return if((a%b!=0L) && ((a<0)!=(b<0))) q-1 else q }
    private fun floorMod(a:Long, b:Long):Long = a-floorDiv(a,b)*b
}
