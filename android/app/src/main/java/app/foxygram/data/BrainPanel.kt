package app.foxygram.data

import org.json.JSONArray
import org.json.JSONObject

/** How a message Brain analysed is marked in the chat. */
enum class BrainMark { Working, Waiting, Failed, Done }

data class BrainPanelJob(val id: String, val name: String, val paused: Boolean)

/** Something Brain proposed: a message to send (approval) or a question to the owner (escalation). */
data class BrainAction(
    val id: Long,
    val kind: String,
    val actionType: String,
    val status: String,
    val to: String?,
    val text: String?,
    val question: String?,
    val options: List<String>,
    val reason: String?,
    val answer: String?,
    val result: String?,
) {
    val isQuestion: Boolean get() = kind == "escalation"
    val isOpen: Boolean get() = status == "open"

    /** A reply Brain would have sent, kept because sending is off for this chat. It is never sent. */
    val isUnsent: Boolean get() = status == "not_sent"
}

/** One agent run started by this chat's messages, with its follow-ups folded in. Message ids are TDLib's. */
data class BrainRun(
    val runId: Long,
    val jobName: String,
    val at: String,
    val messageIds: List<Long>,
    val status: String,
    val working: Boolean,
    val decisions: List<String>,
    val actions: List<BrainAction>,
    val summary: String,
)

/** A document or check on a load, already worded by the server. [tone]: ok, asked, problem, plain or missing. */
data class BrainLoadCheck(val label: String, val tone: String, val detail: String)

/** Something a person asked for on a load and is still waiting on. [old] after about four hours. */
data class BrainLoadWait(val what: String, val line: String, val at: String, val old: Boolean)

/** One line of a load's history. [messageIds] are TDLib's. */
data class BrainLoadEvent(val text: String, val by: String, val at: String, val stage: String?, val runId: Long?, val messageIds: List<Long>)

data class BrainLoadStop(val text: String, val done: Boolean)

/**
 * A load Brain follows in this chat, shaped by the server: stage and progress ([step] of [steps], 0 when cancelled),
 * route, documents, what someone is waiting for, numbers and the latest history (oldest first).
 */
data class BrainLoad(
    val id: Long,
    val name: String,
    val stage: String,
    val stageTitle: String,
    val stageAbout: String,
    val step: Int,
    val steps: Int,
    val open: Boolean,
    val route: String,
    val meta: List<String>,
    val stops: List<BrainLoadStop>,
    val checks: List<BrainLoadCheck>,
    val waiting: List<BrainLoadWait>,
    val numbers: List<Pair<String, String>>,
    val events: List<BrainLoadEvent>,
    val updatedAgo: String,
    val closedAt: String?,
) {
    fun mentions(messageIds: Collection<Long>): Boolean = events.any { event -> event.messageIds.any { it in messageIds } }
}

/**
 * Brain's side panel for a chat. Only chats in at least one of Brain's jobs are active.
 * [waiting] holds messages Brain has received but not started on yet (it waits about 20 s for more), as TDLib ids.
 * [sending] is false when the owner switched sending off: Brain only shows what it would have answered.
 * [loads] is null when no job of this chat follows loads.
 */
data class BrainPanel(
    val active: Boolean,
    val jobs: List<BrainPanelJob>,
    val items: List<BrainRun>,
    val waiting: List<Long> = emptyList(),
    val sending: Boolean = true,
    val loads: List<BrainLoad>? = null,
) {
    /** The loads Brain recorded from these messages. */
    fun loadsFor(messageIds: Collection<Long>): List<BrainLoad> = loads.orEmpty().filter { it.mentions(messageIds) }

    val pausedJobs: List<BrainPanelJob> get() = jobs.filter { it.paused }

    /** Brain is busy: a run is going, or it holds messages it hasn't started on. */
    val busy: Boolean get() = waiting.isNotEmpty() || items.any { it.working }

    fun runsFor(messageIds: Collection<Long>): List<BrainRun> = items.filter { run -> run.messageIds.any { it in messageIds } }

    fun isWaiting(messageIds: Collection<Long>): Boolean = messageIds.any { it in waiting }

    /** The mark each analysed message gets: still working, waiting for the owner, failed, or done. */
    fun marks(): Map<Long, BrainMark> {
        val marks = HashMap<Long, BrainMark>()
        for (run in items) {
            val mark = when {
                run.working -> BrainMark.Working
                run.actions.any { it.isOpen } -> BrainMark.Waiting
                run.status == "error" || run.actions.any { it.status == "failed" } -> BrainMark.Failed
                else -> BrainMark.Done
            }
            for (id in run.messageIds) {
                val current = marks[id]
                if (current == null || mark.ordinal < current.ordinal) marks[id] = mark
            }
        }
        for (id in waiting) marks[id] = BrainMark.Working
        return marks
    }
}

private fun JSONObject.text(key: String): String? = if (!has(key) || isNull(key)) null else optString(key).ifBlank { null }

private fun JSONArray?.strings(): List<String> = if (this == null) emptyList() else (0 until length()).map { optString(it) }

fun parseBrainPanel(body: String): BrainPanel {
    val json = JSONObject(body)
    val jobs = json.optJSONArray("jobs") ?: JSONArray()
    val items = json.optJSONArray("items") ?: JSONArray()
    return BrainPanel(
        active = json.optBoolean("active"),
        jobs = (0 until jobs.length()).map { index ->
            jobs.getJSONObject(index).let { BrainPanelJob(it.getString("id"), it.optString("name", it.getString("id")), it.optBoolean("paused")) }
        },
        items = (0 until items.length()).map { index -> parseRun(items.getJSONObject(index)) },
        waiting = json.optJSONArray("waiting")?.let { ids -> (0 until ids.length()).map { ids.getLong(it) } } ?: emptyList(),
        sending = json.optBoolean("sending", true),
        loads = json.optJSONArray("loads")?.let { loads -> (0 until loads.length()).map { parseLoad(loads.getJSONObject(it)) } },
    )
}

private fun JSONArray?.objects(): List<JSONObject> = if (this == null) emptyList() else (0 until length()).map { getJSONObject(it) }

private fun JSONArray?.longs(): List<Long> = if (this == null) emptyList() else (0 until length()).map { getLong(it) }

private fun parseLoad(load: JSONObject): BrainLoad = BrainLoad(
    id = load.optLong("id"),
    name = load.text("name") ?: "Load #${load.optLong("id")}",
    stage = load.optString("stage"),
    stageTitle = load.text("stageTitle") ?: load.optString("stage"),
    stageAbout = load.text("stageAbout").orEmpty(),
    step = load.optInt("step"),
    steps = load.optInt("steps", 8),
    open = load.optBoolean("open", true),
    route = load.text("route").orEmpty(),
    meta = load.optJSONArray("meta").strings().filter { it.isNotBlank() },
    stops = load.optJSONArray("stops").objects().map { BrainLoadStop(it.optString("text"), it.optBoolean("done")) },
    checks = load.optJSONArray("checks").objects().map { BrainLoadCheck(it.optString("label"), it.optString("tone"), it.optString("detail")) },
    waiting = load.optJSONArray("waiting").objects().map {
        BrainLoadWait(it.optString("what"), it.optString("line"), it.optString("at"), it.optBoolean("old"))
    },
    numbers = load.optJSONArray("numbers").objects().map { it.optString("label") to it.optString("value") },
    events = load.optJSONArray("events").objects().map {
        BrainLoadEvent(
            text = it.optString("text"),
            by = it.optString("by", "brain"),
            at = it.optString("at"),
            stage = it.text("stage"),
            runId = if (it.has("runId") && !it.isNull("runId")) it.optLong("runId") else null,
            messageIds = it.optJSONArray("messageIds").longs(),
        )
    },
    updatedAgo = load.text("updatedAgo").orEmpty(),
    closedAt = load.text("closedAt"),
)

private fun parseRun(run: JSONObject): BrainRun {
    val ids = run.optJSONArray("messageIds") ?: JSONArray()
    val decisions = run.optJSONArray("decisions") ?: JSONArray()
    val actions = run.optJSONArray("actions") ?: JSONArray()
    return BrainRun(
        runId = run.getLong("runId"),
        jobName = run.text("jobName") ?: run.optString("job"),
        at = run.optString("at"),
        messageIds = (0 until ids.length()).map { ids.getLong(it) },
        status = run.optString("status"),
        working = run.optBoolean("working"),
        decisions = (0 until decisions.length()).mapNotNull { decisions.getJSONObject(it).text("text") },
        actions = (0 until actions.length()).map { index ->
            actions.getJSONObject(index).let { action ->
                BrainAction(
                    id = action.getLong("id"),
                    kind = action.optString("kind"),
                    actionType = action.text("actionType").orEmpty(),
                    status = action.optString("status"),
                    to = action.text("to"),
                    text = action.text("text"),
                    question = action.text("question"),
                    options = action.optJSONArray("options").strings(),
                    reason = action.text("reason"),
                    answer = action.text("answer"),
                    result = action.text("result"),
                )
            }
        },
        summary = run.text("summary").orEmpty(),
    )
}
