package app.algoroutine.core

import kotlin.test.*

class ExecutionEngineTest {
    @Test fun initialViewDoesNotCompleteAnything() {
        val engine = DemoFactory().create()
        repeat(3) { assertEquals("open", engine.view().currentStepId) }
        assertEquals(0, engine.view().completedCount)
    }
    @Test fun explicitCompletionShowsNext() {
        val engine = DemoFactory().create()
        val result = engine.complete("one", "open", 0)
        assertTrue(result.accepted)
        assertEquals("가제 한 줄 적기", result.view.currentTitle)
        assertEquals(1, result.view.completedCount)
    }
    @Test fun replayDoesNotAdvanceAgain() {
        val engine = DemoFactory().create()
        val original = engine.complete("one", "open", 0)
        assertEquals(original, engine.complete("one", "open", 0))
        assertEquals(1, engine.view().completedCount)
    }
    @Test fun sameCommandDifferentTargetRejected() {
        val engine = DemoFactory().create()
        engine.complete("one", "open", 0)
        assertEquals("COMMAND_CONFLICT", engine.complete("one", "title", 1).reason)
        assertEquals(1, engine.view().completedCount)
    }
    @Test fun staleFingerCannotCompleteNextStep() {
        val engine = DemoFactory().create()
        engine.complete("one", "open", 0)
        assertFalse(engine.complete("two", "open", 0).accepted)
        assertEquals("title", engine.view().currentStepId)
    }
    @Test fun wrongTargetRejected() {
        val engine = DemoFactory().create()
        assertFalse(engine.complete("one", "keywords", 0).accepted)
        assertEquals(0, engine.view().completedCount)
    }
    @Test fun allRequiredStepsFinishExactlyOnce() {
        val engine = DemoFactory().create()
        listOf("open", "title", "keywords").forEachIndexed { i, step ->
            assertTrue(engine.complete("c$i", step, i).accepted)
        }
        assertTrue(engine.view().finished)
        assertNull(engine.view().currentStepId)
        assertEquals("다음 작업 없음", engine.view().currentTitle)
        assertFalse(engine.complete("late", "keywords", 3).accepted)
        assertEquals(3, engine.view().completedCount)
    }
    @Test fun invalidDefinitionRejected() {
        assertFailsWith<IllegalArgumentException> { ExecutionEngine("x", "t", emptyList()) }
        assertFailsWith<IllegalArgumentException> { ExecutionEngine("x", "t", listOf(RoutineStep("a", "A"), RoutineStep("a", "B"))) }
    }
    @Test fun inputListMutationDoesNotChangeOccurrence() {
        val steps = mutableListOf(RoutineStep("a", "A"), RoutineStep("b", "B"))
        val engine = ExecutionEngine("x", "t", steps)
        steps.clear()
        assertEquals(2, engine.view().totalCount)
    }
}
