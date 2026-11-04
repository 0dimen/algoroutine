package app.algoroutine.core

import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

/** Native adapters must distinguish missing data from a read error, and replace atomically. */
data class StorageRead(val content: String?, val error: Boolean)
interface ExecutionStorage {
    fun read(): StorageRead
    fun write(content: String): Boolean
}

@Serializable
data class OccurrenceDefinition(
    val occurrenceId: String, val definitionId: String, val definitionVersion: Int,
    val parentTitle: String, val authorName: String, val steps: List<RoutineStep>,
)
@Serializable
private data class SavedCommand(val id: String, val stepId: String, val revision: Int)
@Serializable
private data class Journal(val schemaVersion: Int, val definition: OccurrenceDefinition, val commands: List<SavedCommand>)

/** Single serialized caller, one local occurrence. Not a multi-device database. */
class PersistentExecution internal constructor(private val storage: ExecutionStorage) {
    private var journal: Journal? = null
    private var engine: ExecutionEngine? = null
    var error: String? = null
        private set
    fun view(): ExecutionView? = engine?.view()
    fun definition(): OccurrenceDefinition? = journal?.definition?.let { it.copy(steps = it.steps.toList()) }

    internal fun open(initial: OccurrenceDefinition) {
        val read = storage.read()
        if (read.error) { error = "READ_FAILED"; return }
        try {
            val candidate = if (read.content == null) Journal(1, initial.copy(steps = initial.steps.toList()), emptyList())
                else Json.decodeFromString<Journal>(read.content)
            val restored = restore(candidate)
            if (read.content == null && !storage.write(Json.encodeToString(candidate))) {
                error = "PERSISTENCE_UNCONFIRMED"; return
            }
            journal = candidate; engine = restored
        } catch (_: Exception) { error = "INVALID_SAVED_STATE" }
    }

    fun complete(commandId: String, targetStepId: String, expectedRevision: Int): CompletionResult? {
        if (error != null) return null // Unknown commit outcome requires reopening before another mutation.
        val current = journal ?: return null
        val candidateEngine = restore(current)
        val command = SavedCommand(commandId, targetStepId, expectedRevision)
        val result = candidateEngine.complete(commandId, targetStepId, expectedRevision)
        // Replays and payload conflicts never rewrite the file or advance state.
        if (current.commands.any { it.id == commandId } || commandId.isBlank()) return result
        if (current.commands.size >= 10000) { error = "JOURNAL_LIMIT"; return null }
        val candidate = current.copy(commands = current.commands + command)
        if (!storage.write(Json.encodeToString(candidate))) {
            error = "PERSISTENCE_UNCONFIRMED"; return null
        }
        journal = candidate; engine = candidateEngine
        return result
    }

    private fun restore(saved: Journal): ExecutionEngine {
        require(saved.schemaVersion == 1)
        val d = saved.definition
        require(d.definitionId.isNotBlank() && d.definitionVersion > 0 && d.authorName.isNotBlank())
        require(saved.commands.size <= 10000 && saved.commands.all { it.id.isNotBlank() })
        require(saved.commands.map { it.id }.toSet().size == saved.commands.size)
        val result = ExecutionEngine(d.occurrenceId, d.parentTitle, d.steps)
        saved.commands.forEach { result.complete(it.id, it.stepId, it.revision) }
        return result
    }
}

class PersistentFactory {
    fun open(storage: ExecutionStorage, initial: OccurrenceDefinition): PersistentExecution =
        PersistentExecution(storage).also { it.open(initial) }
    fun openDemo(storage: ExecutionStorage): PersistentExecution = open(storage, OccurrenceDefinition(
        "persistent-demo-v1", "report-starter", 1, "보고서 초안 시작", "데모 라이브러리",
        listOf(RoutineStep("open", "문서 열기"), RoutineStep("title", "가제 한 줄 적기"), RoutineStep("keywords", "키워드 세 개 적기")),
    ))
}
