package app.foxygram.data

import app.foxygram.model.CaseEvent
import app.foxygram.model.CaseMessage
import app.foxygram.model.CaseSummary
import app.foxygram.model.ChatLabel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

data class ServerHealth(val claudeState: String, val claudeDetail: String, val callsToday: Int, val pending: Int)

data class ProjectInfo(val id: Long, val name: String, val color: Long, val categories: List<Pair<Long, String>>)

data class AiChat(val chatId: Long, val title: String, val kind: String, val enabled: Boolean, val projectId: Long?, val categoryId: Long?)

data class BrainJob(val id: String, val name: String)

/** Which of Brain's jobs get a chat: all of them, those a Telegram folder brings, and the owner's own changes. */
data class BrainChat(val jobs: List<String>, val viaFolder: List<String>, val added: List<String>, val removed: List<String>)

data class BrainJobs(val jobs: List<BrainJob>, val connected: Boolean, val chat: BrainChat)

data class BrainChange(val text: String, val chat: BrainChat)

class ServerError(message: String) : Exception(message)

/** The laptop. It may be off or asleep at any moment, so every caller must cope with failure. */
class ServerApi(private val settings: Settings) {
    val configured: Boolean get() = settings.serverUrl.isNotBlank() && settings.serverToken.isNotBlank()

    private suspend fun request(method: String, path: String, body: JSONObject? = null): String = withContext(Dispatchers.IO) {
        val connection = (URL(settings.serverUrl + path).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = TIMEOUT_MS
            readTimeout = TIMEOUT_MS
            setRequestProperty("Authorization", "Bearer ${settings.serverToken}")
            setRequestProperty("Content-Type", "application/json")
        }
        try {
            if (body != null) {
                connection.doOutput = true
                connection.outputStream.use { it.write(body.toString().toByteArray()) }
            }
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
            // The server explains problems in "detail", such as Brain not running; show that rather than a code.
            if (code !in 200..299) {
                val detail = runCatching { JSONObject(text).opt("detail") as? String }.getOrNull()
                throw ServerError(detail?.ifBlank { null } ?: "HTTP $code")
            }
            text
        } finally {
            connection.disconnect()
        }
    }

    suspend fun health(): ServerHealth {
        val json = JSONObject(request("GET", "/v1/health"))
        val claude = json.getJSONObject("claude")
        return ServerHealth(claude.getString("state"), claude.getString("detail"), claude.getInt("calls_today"), json.getInt("pending"))
    }

    suspend fun labels(): Map<Long, ChatLabel> {
        val rows = JSONArray(request("GET", "/v1/flags"))
        return (0 until rows.length()).associate { index ->
            val row = rows.getJSONObject(index)
            row.getLong("chat_id") to ChatLabel(
                needsReply = row.optInt("needs_reply") == 1,
                urgent = row.optString("urgency") == "high",
                projectName = row.nullableString("project_name"),
                projectColor = row.nullableString("project_color")?.let(::parseColor),
                categoryName = row.nullableString("category_name"),
                caseId = if (row.isNull("case_id")) null else row.getLong("case_id"),
                caseTitle = row.nullableString("case_title"),
                aiEnabled = row.optInt("ai_enabled") == 1,
            )
        }
    }

    suspend fun chats(): List<AiChat> {
        val rows = JSONArray(request("GET", "/v1/chats"))
        return (0 until rows.length()).map { index ->
            val row = rows.getJSONObject(index)
            AiChat(
                row.getLong("chat_id"), row.getString("title"), row.getString("kind"), row.optInt("ai_enabled") == 1,
                if (row.isNull("project_id")) null else row.getLong("project_id"),
                if (row.isNull("category_id")) null else row.getLong("category_id"),
            )
        }
    }

    suspend fun setAiEnabled(chatId: Long, enabled: Boolean) {
        request("POST", "/v1/chats/$chatId", JSONObject().put("ai_enabled", enabled))
    }

    suspend fun setProject(chatId: Long, projectId: Long?) {
        request("POST", "/v1/chats/$chatId", JSONObject().put("project_id", projectId ?: JSONObject.NULL))
    }

    suspend fun setCategory(chatId: Long, categoryId: Long?) {
        request("POST", "/v1/chats/$chatId", JSONObject().put("category_id", categoryId ?: JSONObject.NULL))
    }

    suspend fun projects(): List<ProjectInfo> {
        val rows = JSONArray(request("GET", "/v1/projects"))
        return (0 until rows.length()).map { index ->
            val row = rows.getJSONObject(index)
            val categories = row.getJSONArray("categories")
            ProjectInfo(
                row.getLong("id"), row.getString("name"), parseColor(row.getString("color")),
                (0 until categories.length()).map { categories.getJSONObject(it).let { c -> c.getLong("id") to c.getString("name") } },
            )
        }
    }

    suspend fun addProject(name: String): Long =
        JSONObject(request("POST", "/v1/projects", JSONObject().put("name", name))).getLong("id")

    suspend fun addCategory(projectId: Long, name: String): Long =
        JSONObject(request("POST", "/v1/projects/$projectId/categories", JSONObject().put("name", name))).getLong("id")

    suspend fun cases(status: String = "open", query: String = ""): List<CaseSummary> {
        val encoded = java.net.URLEncoder.encode(query, "UTF-8")
        val rows = JSONArray(request("GET", "/v1/cases?status=$status&q=$encoded"))
        return (0 until rows.length()).map { parseCase(rows.getJSONObject(it)) }
    }

    suspend fun caseEvents(caseId: Long): Pair<CaseSummary, List<CaseEvent>> {
        val json = JSONObject(request("GET", "/v1/cases/$caseId"))
        val timeline = json.getJSONArray("timeline")
        val events = (0 until timeline.length()).map { index ->
            val row = timeline.getJSONObject(index)
            val messages = row.getJSONArray("messages")
            CaseEvent(
                burstId = row.getLong("burst_id"),
                chatId = row.getLong("chat_id"),
                chatTitle = row.optString("chat_title"),
                createdAt = row.getLong("created_at"),
                intent = row.nullableString("intent").orEmpty(),
                needsReply = row.optInt("needs_reply") == 1,
                urgency = row.nullableString("urgency").orEmpty(),
                summary = row.nullableString("summary").orEmpty(),
                needsReview = row.optInt("needs_review") == 1,
                messages = (0 until messages.length()).map { i ->
                    val m = messages.getJSONObject(i)
                    CaseMessage(m.getLong("message_id"), m.getLong("date"), m.optString("sender_name"), m.optInt("outgoing") == 1, m.optString("text"))
                },
            )
        }
        return parseCase(json) to events
    }

    suspend fun setCaseStatus(caseId: Long, status: String) {
        request("POST", "/v1/cases/$caseId", JSONObject().put("status", status))
    }

    suspend fun renameCase(caseId: Long, title: String) {
        request("POST", "/v1/cases/$caseId", JSONObject().put("title", title))
    }

    suspend fun confirmLink(burstId: Long) {
        request("POST", "/v1/bursts/$burstId/confirm", JSONObject())
    }

    suspend fun unlink(burstId: Long) {
        request("POST", "/v1/bursts/$burstId/move", JSONObject())
    }

    /** Brain jobs go through the laptop, which holds Brain's token; the phone never sees it. */
    suspend fun brainJobs(chatId: Long): BrainJobs {
        val json = JSONObject(request("GET", "/v1/brain/chats/$chatId"))
        val jobs = json.getJSONArray("jobs")
        return BrainJobs(
            jobs = (0 until jobs.length()).map { jobs.getJSONObject(it).let { j -> BrainJob(j.getString("id"), j.getString("name")) } },
            connected = json.optBoolean("connected", true),
            chat = parseBrainChat(json.getJSONObject("chat")),
        )
    }

    suspend fun setBrainJob(chatId: Long, jobId: String, on: Boolean): BrainChange =
        parseBrainChange(request("POST", "/v1/brain/chats/$chatId/jobs", JSONObject().put("job_id", jobId).put("on", on)))

    /** Forgets the owner's own changes for this chat, so only Telegram folders decide. */
    suspend fun resetBrainJobs(chatId: Long): BrainChange =
        parseBrainChange(request("POST", "/v1/brain/chats/$chatId/reset", JSONObject()))

    private fun parseBrainChange(text: String): BrainChange {
        val json = JSONObject(text)
        return BrainChange(json.optString("text"), parseBrainChat(json.getJSONObject("chat")))
    }

    private fun parseBrainChat(json: JSONObject): BrainChat {
        fun ids(key: String): List<String> {
            val array = json.optJSONArray(key) ?: return emptyList()
            return (0 until array.length()).map { array.getString(it) }
        }
        return BrainChat(ids("jobs"), ids("viaFolder"), ids("added"), ids("removed"))
    }

    private fun parseCase(json: JSONObject): CaseSummary {
        val chats = json.getJSONArray("chats")
        val entities = json.getJSONArray("entities")
        return CaseSummary(
            id = json.getLong("id"),
            title = json.getString("title"),
            summary = json.optString("summary"),
            status = json.optString("status"),
            updatedAt = json.getLong("updated_at"),
            chats = (0 until chats.length()).map { chats.getJSONObject(it).optString("title") },
            entities = (0 until entities.length()).map { entities.getJSONObject(it).getString("value") },
            needsReview = json.optInt("needs_review"),
        )
    }

    private fun JSONObject.nullableString(key: String): String? = if (isNull(key)) null else optString(key).ifBlank { null }

    private fun parseColor(hex: String): Long = 0xFF000000L or hex.removePrefix("#").toLong(16)

    private companion object {
        const val TIMEOUT_MS = 8_000
    }
}
