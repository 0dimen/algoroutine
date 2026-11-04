package app.algoroutine.core

import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

@Serializable data class RunDefinition(val id: String, val version: Int, val title: String, val author: String, val steps: List<RoutineStep>, val windowStartMillis:Long?=null, val windowEndMillis:Long?=null, val description:String="")
@Serializable data class RunCommand(
    val id: String, val kind: String, val occurrenceId: String, val expectedRevision: Int,
    val unitId: String? = null, val expectedFocusRevision: Int? = null, val definition: RunDefinition? = null,
)
@Serializable data class StepView(val id: String, val title: String, val status: String)
@Serializable data class RunView(
    val id: String, val definition: RunDefinition, val revision: Int, val status: String,
    val currentUnitId: String?, val completed: Int, val skipped: Int, val evidence: String?, val steps: List<StepView>, val order: List<String> = emptyList(),
)
@Serializable data class WorkspaceView(val revision: Int, val focusRevision: Int, val focusId: String?, val runs: List<RunView>)
@Serializable data class RunResult(val accepted: Boolean, val reason: String, val view: WorkspaceView)
@Serializable data class RunEvent(val commandId: String, val kind: String, val occurrenceId: String, val unitId: String?, val atMillis: Long)
@Serializable private data class Entry(val command: RunCommand, val atMillis: Long)
@Serializable private data class WorkspaceJournal(val schemaVersion: Int = 2, val entries: List<Entry>)

/** All execution decisions live here. The server/UI supplies identity and an observed clock. */
class WorkspaceEngine {
    private data class Run(val id: String, val definition: RunDefinition, val queue: MutableList<String>, val statuses: MutableMap<String,String>, var revision: Int = 0, var status: String = "running", var evidence: String? = null, val order: MutableList<String> = queue.toMutableList())
    private val runs = linkedMapOf<String,Run>()
    private val receipts = linkedMapOf<String,Pair<RunCommand,RunResult>>()
    private val events = mutableListOf<RunEvent>()
    private var revision = 0
    private var focusRevision = 0
    private var focusId: String? = null
    fun view() = WorkspaceView(revision, focusRevision, focusId, runs.values.map { r ->
        RunView(r.id, r.definition.copy(steps=r.definition.steps.toList()), r.revision,r.status,r.queue.firstOrNull(),r.statuses.values.count{it=="completed"},r.statuses.values.count{it=="skipped"},r.evidence,
            r.definition.steps.map{StepView(it.id,it.title,r.statuses.getValue(it.id))}, r.order.toList())
    })
    fun events(): List<RunEvent> = events.toList()
    fun execute(input: RunCommand, atMillis: Long): RunResult {
        val c = input.copy(definition=input.definition?.let { it.copy(steps=it.steps.toList()) })
        receipts[c.id]?.let { return if(it.first==c) it.second else RunResult(false,"COMMAND_CONFLICT",view()) }
        fun reject(reason: String): RunResult {
            val result=RunResult(false,reason,view()); if(c.id.isNotBlank()) receipts[c.id]=c to result; return result
        }
        if(c.id.isBlank() || c.occurrenceId.isBlank() || atMillis<0) return reject("INVALID_COMMAND")
        when(c.kind) {
            "start" -> {
                if(c.expectedRevision!=revision) return reject("STALE_REVISION")
                if(c.unitId!=null || c.expectedFocusRevision!=null) return reject("INVALID_COMMAND")
                val d=c.definition ?: return reject("INVALID_DEFINITION")
                // Zero steps = a plain schedule: only with a time window; it stays running until Done (completeParent) or its end.
                if(d.id.isBlank() || d.version<1 || d.title.isBlank() || d.author.isBlank() || (d.steps.isEmpty() && d.windowStartMillis==null) || d.steps.size>50 || d.steps.any{it.id.isBlank()||it.title.isBlank()} || d.steps.map{it.id}.toSet().size!=d.steps.size) return reject("INVALID_DEFINITION")
                if((d.windowStartMillis==null)!=(d.windowEndMillis==null) || (d.windowStartMillis!=null && d.windowStartMillis>=d.windowEndMillis!!)) return reject("INVALID_WINDOW")
                if(d.windowStartMillis!=null && atMillis<d.windowStartMillis)return reject("EARLY_START")
                if(d.windowEndMillis!=null && atMillis>=d.windowEndMillis)return reject("WINDOW_ELAPSED")
                if(runs.containsKey(c.occurrenceId)) return reject("OCCURRENCE_EXISTS")
                runs[c.occurrenceId]=Run(c.occurrenceId,d,d.steps.map{it.id}.toMutableList(),d.steps.associate{it.id to "pending"}.toMutableMap())
                focusId=c.occurrenceId;focusRevision++
            }
            "expire" -> {
                val r=runs[c.occurrenceId] ?: return reject("NOT_FOUND")
                if(c.id!="system:elapsed:${r.id}" || c.definition!=null || c.unitId!=null || c.expectedFocusRevision!=null) return reject("INVALID_COMMAND")
                if(c.expectedRevision!=r.revision) return reject("STALE_REVISION")
                val end=r.definition.windowEndMillis ?: return reject("NO_WINDOW")
                if(atMillis<end) return reject("WINDOW_ACTIVE")
                if(r.status!="running") return reject("ALREADY_ENDED")
                r.queue.forEach{r.statuses[it]="elapsed"};r.queue.clear()
                r.status="elapsed";r.evidence="window_elapsed";r.revision++
            }
            "focus" -> {
                if(c.expectedRevision!=revision) return reject("STALE_REVISION")
                if(c.definition!=null || c.unitId!=null || c.expectedFocusRevision!=null) return reject("INVALID_COMMAND")
                val r=runs[c.occurrenceId] ?: return reject("NOT_FOUND")
                if(r.status!="running" || (r.definition.windowEndMillis!=null && atMillis>=r.definition.windowEndMillis)) return reject("FOCUS_TARGET_ENDED")
                if(focusId==r.id) return reject("ALREADY_FOCUSED")
                focusId=r.id;focusRevision++
            }
            "complete", "defer", "skip", "completeParent" -> {
                if(c.definition!=null) return reject("INVALID_COMMAND")
                val r=runs[c.occurrenceId] ?: return reject("NOT_FOUND")
                if(c.expectedFocusRevision!=focusRevision || focusId!=r.id) return reject("FOCUS_CHANGED")
                if(r.status=="elapsed" || (r.definition.windowEndMillis!=null && atMillis>=r.definition.windowEndMillis))return reject("WINDOW_ELAPSED")
                if(c.expectedRevision!=r.revision) return reject("STALE_REVISION")
                if(r.status=="completed") return reject("ALREADY_COMPLETED")
                if(c.kind=="completeParent") {
                    if(c.unitId!=null) return reject("WRONG_TARGET")
                    r.queue.forEach { r.statuses[it]="excluded" };r.queue.clear()
                    r.status="completed";r.evidence="direct_parent"
                } else {
                    if(r.status!="running" || r.queue.isEmpty() || c.unitId!=r.queue.first()) return reject("WRONG_TARGET")
                    val id=r.queue.first()
                    when(c.kind) {
                        "defer" -> {
                            if(r.queue.size<2) return reject("NO_NEXT_UNIT")
                            val next=r.queue[1];val a=r.order.indexOf(id);val b=r.order.indexOf(next);r.order[a]=next;r.order[b]=id
                            r.queue.removeAt(0);r.queue.add(1,id)
                        }
                        "skip" -> {r.queue.removeAt(0);r.statuses[id]="skipped"}
                        "complete" -> {r.queue.removeAt(0);r.statuses[id]="completed"}
                    }
                    if(r.queue.isEmpty()) {
                        if(r.statuses.values.all{it=="completed"}) {r.status="completed";r.evidence="required_children"}
                        else r.status="exhausted" // Skipped != completed. Parent may still be explicitly completed.
                    }
                }
                r.revision++
            }
            else -> return reject("UNKNOWN_COMMAND")
        }
        revision++;events+=RunEvent(c.id,c.kind,c.occurrenceId,c.unitId,atMillis)
        val result=RunResult(true,"APPLIED",view());receipts[c.id]=c to result;return result
    }
}

/** One serial owner must hold storage for the entire read/mutate/atomic-replace transaction. */
class WorkspaceStore(private val storage: ExecutionStorage) {
    private var entries=emptyList<Entry>()
    private var engine=WorkspaceEngine()
    var error: String?=null; private set
    init {
        try {
            val read=storage.read()
            if(read.error) error="READ_FAILED"
            else if(read.content!=null) {
                val saved=Json.decodeFromString<WorkspaceJournal>(read.content)
                require(saved.schemaVersion in 2..3 && saved.entries.size<=10000)
                require(saved.entries.all{it.command.id.isNotBlank()} && saved.entries.map{it.command.id}.toSet().size==saved.entries.size)
                entries=saved.entries;engine=replay(entries)
            }
        } catch(_:Exception) {error="INVALID_SAVED_STATE"}
    }
    fun view()=engine.view()
    fun events()=engine.events()
    /** Persist overdue runs once, including catch-up after process downtime. Never completes a step. */
    fun reconcile(atMillis:Long):Boolean {
        if(error!=null)return false
        for(r in view().runs.filter{it.status=="running" && it.definition.windowEndMillis?.let{end->atMillis>=end}==true}) {
            val result=execute(RunCommand("system:elapsed:${r.id}","expire",r.id,r.revision),atMillis) ?: return false
            if(!result.accepted){error="EXPIRY_REJECTED";return false}
        }
        return true
    }
    fun savedCommand(id:String):RunCommand?=entries.firstOrNull{it.command.id==id}?.command
    private fun replay(items:List<Entry>)=WorkspaceEngine().also{e->items.forEach{e.execute(it.command,it.atMillis)}}
    fun execute(command:RunCommand, atMillis:Long):RunResult? {
        if(error!=null)return null
        val candidate=replay(entries);val result=candidate.execute(command,atMillis)
        if(entries.any{it.command.id==command.id} || command.id.isBlank())return result
        if(entries.size>=10000){error="JOURNAL_LIMIT";return null}
        val frozen=command.copy(definition=command.definition?.let{it.copy(steps=it.steps.toList())})
        val next=entries+Entry(frozen,atMillis)
        if(!storage.write(Json.encodeToString(WorkspaceJournal(schemaVersion=3,entries=next)))){error="PERSISTENCE_UNCONFIRMED";return null}
        entries=next;engine=candidate;return result
    }
}
