package app.algoroutine.core

/** The UI carries IDs and revisions; it never selects the next step itself. */
@kotlinx.serialization.Serializable
data class RoutineStep(val id: String, val title: String)
data class ExecutionView(
    val occurrenceId: String,
    val parentTitle: String,
    val currentStepId: String?,
    val currentTitle: String,
    val completedCount: Int,
    val totalCount: Int,
    val revision: Int,
    val finished: Boolean,
)
data class CompletionResult(val accepted: Boolean, val reason: String, val view: ExecutionView)

class ExecutionEngine(
    private val occurrenceId: String,
    private val parentTitle: String,
    steps: List<RoutineStep>,
) {
    private val steps = steps.toList()
    private var index = 0
    private var revision = 0
    private data class Command(val stepId: String, val expectedRevision: Int, val result: CompletionResult)
    private val commands = mutableMapOf<String, Command>()

    init {
        require(occurrenceId.isNotBlank() && parentTitle.isNotBlank())
        require(this.steps.isNotEmpty()) { "An empty routine must not auto-complete." }
        require(this.steps.all { it.id.isNotBlank() && it.title.isNotBlank() })
        require(this.steps.map { it.id }.toSet().size == this.steps.size)
    }

    fun view(): ExecutionView = ExecutionView(
        occurrenceId, parentTitle, steps.getOrNull(index)?.id,
        steps.getOrNull(index)?.title ?: "다음 작업 없음", index, steps.size,
        revision, index == steps.size,
    )

    /** Explicit completion only. Replaying one command never completes the next step. */
    fun complete(commandId: String, targetStepId: String, expectedRevision: Int): CompletionResult {
        commands[commandId]?.let {
            return if (it.stepId == targetStepId && it.expectedRevision == expectedRevision) it.result
            else CompletionResult(false, "COMMAND_CONFLICT", view())
        }
        val reason = when {
            commandId.isBlank() -> "INVALID_COMMAND"
            expectedRevision != revision -> "STALE_REVISION"
            index == steps.size -> "FINISHED"
            targetStepId != steps[index].id -> "WRONG_TARGET"
            else -> "COMPLETED"
        }
        if (reason == "COMPLETED") { index += 1; revision += 1 }
        val result = CompletionResult(reason == "COMPLETED", reason, view())
        if (commandId.isNotBlank()) commands[commandId] = Command(targetStepId, expectedRevision, result)
        return result
    }
}

/** Fixture factory shared by both apps; no UI-layer duplicate queue. */
class DemoFactory {
    fun create(): ExecutionEngine = ExecutionEngine("proof-occurrence", "보고서 초안 시작", listOf(
        RoutineStep("open", "문서 열기"),
        RoutineStep("title", "가제 한 줄 적기"),
        RoutineStep("keywords", "키워드 세 개 적기"),
    ))
}
