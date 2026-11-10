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

/** Brain's side panel for a chat. Only chats in at least one of Brain's jobs are active. */
data class BrainPanel(val active: Boolean, val jobs: List<BrainPanelJob>, val items: List<BrainRun>) {
    val pausedJobs: List<BrainPanelJob> get() = jobs.filter { it.paused }

    fun runsFor(messageIds: Collection<Long>): List<BrainRun> = items.filter { run -> run.messageIds.any { it in messageIds } }

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
    )
}

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
