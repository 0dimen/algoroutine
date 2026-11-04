package app.algoroutine.core
import kotlin.test.*

class OrbitScaleTest {
    private val kst = 9*3_600_000L
    /** 2026-11-04 local (KST) hh:mm as epoch millis. */
    private fun at(h:Int, m:Int, s:Int=0):Long = 1793718000000L + (h*3600L+m*60L+s)*1000L - 0L

    @Test fun depthScalesAreTheAgreedValues() {
        assertEquals(listOf(120 to 10, 30 to 5, 10 to 1), OrbitScales.all.map{it.windowMinutes to it.tickMinutes})
        assertEquals(listOf("day","routine","step"), OrbitScales.all.map{it.depth})
        assertSame(OrbitScales.ROUTINE, OrbitScales.forDepth("routine"))
        assertSame(OrbitScales.DAY, OrbitScales.forDepth("unknown"))
    }

    @Test fun dayTicksSitOnRealTenMinuteMarks() {
        val now=at(17,3)
        val ticks=OrbitScales.ticks(OrbitScales.DAY, now, kst)
        // window 16:03..18:03 -> 16:10, 16:20, ... 18:00
        assertEquals(12, ticks.size)
        assertEquals(at(16,10), ticks.first().atMillis); assertEquals(at(18,0), ticks.last().atMillis)
        assertTrue(ticks.all{ it.offset in -1.0..1.0 })
        assertEquals(listOf(at(17,0), at(18,0)), ticks.filter{it.label}.map{it.atMillis})
    }

    @Test fun ticksSlideOneMinuteLater() {
        val a=OrbitScales.ticks(OrbitScales.DAY, at(17,3), kst).first{ it.atMillis==at(17,30) }
        val b=OrbitScales.ticks(OrbitScales.DAY, at(17,4), kst).first{ it.atMillis==at(17,30) }
        // the 17:30 tick moves toward now (0) by exactly 1 min / 60 min half-window
        assertEquals(a.offset-1.0/60, b.offset, 1e-9)
    }

    @Test fun routineAndStepScales() {
        val r=OrbitScales.ticks(OrbitScales.ROUTINE, at(14,2), kst)
        assertEquals(listOf(at(13,50),at(13,55),at(14,0),at(14,5),at(14,10),at(14,15)), r.map{it.atMillis})
        assertEquals(listOf(at(14,0),at(14,15)), r.filter{it.label}.map{it.atMillis})
        val s=OrbitScales.ticks(OrbitScales.STEP, at(14,2,30), kst)
        assertEquals(10, s.size); assertEquals(at(13,58), s.first().atMillis); assertEquals(at(14,7), s.last().atMillis)
    }

    @Test fun nowOnATickIsTheCentre() {
        val t=OrbitScales.ticks(OrbitScales.ROUTINE, at(14,0), kst)
        assertEquals(0.0, t.first{it.atMillis==at(14,0)}.offset)
        assertEquals(-1.0, t.first().offset); assertEquals(1.0, t.last().offset)
        assertNull(OrbitScales.offset(OrbitScales.ROUTINE, at(14,16), at(14,0)))
        assertEquals(0.5, OrbitScales.offset(OrbitScales.ROUTINE, at(14,7,30), at(14,0)))
    }
}
