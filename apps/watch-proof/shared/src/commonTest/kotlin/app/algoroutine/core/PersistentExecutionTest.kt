package app.algoroutine.core

import kotlin.test.*

class PersistentExecutionTest {
    private class Disk : ExecutionStorage {
        var content: String? = null
        var readError = false
        var failWrite = false
        var commitButReportFailure = false
        var writes = 0
        override fun read() = StorageRead(content, readError)
        override fun write(content: String): Boolean {
            writes++
            if (failWrite) return false
            this.content = content
            return !commitButReportFailure
        }
    }
    @Test fun restoresNextAndOriginalCommandResult() {
        val disk = Disk(); val first = PersistentFactory().openDemo(disk)
        val receipt = first.complete("c1", "open", 0)
        first.complete("c2", "title", 1)
        val reopened = PersistentFactory().openDemo(disk)
        assertEquals("keywords", reopened.view()!!.currentStepId)
        val writes = disk.writes
        assertEquals(receipt, reopened.complete("c1", "open", 0))
        assertEquals(writes, disk.writes)
        assertEquals(2, reopened.view()!!.completedCount)
        assertEquals("COMMAND_CONFLICT", reopened.complete("c1", "title", 1)!!.reason)
    }
    @Test fun finalCompletionRemainsFinished() {
        val disk = Disk(); val s = PersistentFactory().openDemo(disk)
        listOf("open", "title", "keywords").forEachIndexed { i, id -> s.complete("c$i", id, i) }
        val reopened = PersistentFactory().openDemo(disk)
        assertTrue(reopened.view()!!.finished)
        assertEquals(3, reopened.view()!!.completedCount)
    }
    @Test fun failedWriteDoesNotAdvanceAndBlocksFreshMutation() {
        val disk = Disk(); val s = PersistentFactory().openDemo(disk); val before = disk.content
        disk.failWrite = true
        assertNull(s.complete("c1", "open", 0))
        assertEquals(0, s.view()!!.completedCount)
        assertEquals(before, disk.content)
        disk.failWrite = false
        assertNull(s.complete("c2", "open", 0))
        assertEquals(0, PersistentFactory().openDemo(disk).view()!!.completedCount)
    }
    @Test fun ambiguousWriteRecoversCommittedResultWithoutCompletingAgain() {
        val disk = Disk(); val s = PersistentFactory().openDemo(disk)
        disk.commitButReportFailure = true
        assertNull(s.complete("c1", "open", 0))
        disk.commitButReportFailure = false
        val reopened = PersistentFactory().openDemo(disk)
        assertEquals(1, reopened.view()!!.completedCount)
        assertTrue(reopened.complete("c1", "open", 0)!!.accepted)
        assertEquals(1, reopened.view()!!.completedCount)
    }
    @Test fun corruptedOrFutureFileIsNeverOverwritten() {
        for (bad in listOf("broken", "", "{\"schemaVersion\":99}")) {
            val disk = Disk(); disk.content = bad
            val s = PersistentFactory().openDemo(disk)
            assertNotNull(s.error); assertNull(s.view()); assertEquals(bad, disk.content); assertEquals(0, disk.writes)
        }
    }
    @Test fun readErrorAndInitialSaveFailureDoNotStartRoutine() {
        val disk = Disk(); disk.readError = true
        assertEquals("READ_FAILED", PersistentFactory().openDemo(disk).error)
        assertEquals(0, disk.writes)
        disk.readError = false; disk.failWrite = true
        val s = PersistentFactory().openDemo(disk)
        assertNull(s.view()); assertEquals("PERSISTENCE_UNCONFIRMED", s.error)
    }
    @Test fun savedDefinitionSurvivesLibraryEditAndInputMutation() {
        val disk = Disk(); val steps = mutableListOf(RoutineStep("a", "사용자 제목"), RoutineStep("b", "다음"))
        val original = OccurrenceDefinition("occ", "def", 2, "원문", "작성자", steps)
        val s = PersistentFactory().open(disk, original); steps.clear(); s.complete("c", "a", 0)
        val edited = original.copy(definitionVersion = 3, parentTitle = "수정", authorName = "다른 작성자", steps = listOf(RoutineStep("z", "변경")))
        val reopened = PersistentFactory().open(disk, edited)
        assertEquals("원문", reopened.view()!!.parentTitle)
        assertEquals("b", reopened.view()!!.currentStepId)
        assertEquals(2, reopened.definition()!!.definitionVersion)
        assertEquals("작성자", reopened.definition()!!.authorName)
    }
    @Test fun rejectedCommandSurvivesRestart() {
        val disk = Disk(); val s = PersistentFactory().openDemo(disk)
        val rejected = s.complete("wrong", "title", 0)
        s.complete("ok", "open", 0)
        val reopened = PersistentFactory().openDemo(disk)
        assertEquals(rejected, reopened.complete("wrong", "title", 0))
        assertEquals("STALE_REVISION", reopened.complete("old", "open", 0)!!.reason)
        assertEquals(1, reopened.view()!!.completedCount)
    }
}
