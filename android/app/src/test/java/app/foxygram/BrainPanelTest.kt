package app.foxygram

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.unit.dp
import app.foxygram.data.BrainMark
import app.foxygram.data.parseBrainPanel
import app.foxygram.ui.brain.BrainMessagePreview
import app.foxygram.ui.brain.BrainPanelContent
import app.foxygram.ui.brain.brainTime
import app.foxygram.ui.theme.Foxy
import app.foxygram.ui.theme.FoxyTheme
import app.foxygram.ui.theme.ThemeMode
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** The server's /v1/brain/chats/{id}/panel answer, shaped like Brain's real one for Test Group. */
private val PANEL = """
{"active": true, "jobs": [{"id": "job2", "name": "Job 2 - Datatruck", "paused": true}],
 "items": [
  {"runId": 13, "job": "job2", "jobName": "Job 2 - Datatruck", "at": "2026-11-10 18:32:05", "telegramMessageIds": [103],
   "messageIds": [108003328], "status": "done", "working": false,
   "decisions": [{"runId": 13, "at": "2026-11-10 18:32:05", "text": "This is a question I cannot answer alone. I will ask the owner."}],
   "actions": [{"id": 9, "runId": 13, "kind": "escalation", "actionType": "escalate", "status": "open", "statusText": "Waiting for you",
     "to": null, "text": null, "question": "How should I answer \"Can I take the load to Dallas tomorrow?\"",
     "options": ["Say yes", "Say no"], "reason": null, "answer": null, "result": null, "createdAt": "2026-11-10 18:32:05", "resolvedAt": null}],
   "summary": "Asked the owner."},
  {"runId": 6, "job": "job2", "jobName": "Job 2 - Datatruck", "at": "2026-11-10 18:31:18", "telegramMessageIds": [101, 102],
   "messageIds": [105906176, 106954752], "status": "done", "working": false,
   "decisions": [{"runId": 6, "at": "2026-11-10 18:31:18", "text": "This needs a reply. I will draft one and ask the owner to approve it."}],
   "actions": [{"id": 3, "runId": 6, "kind": "approval", "actionType": "telegram.send", "status": "open", "statusText": "Waiting for you",
     "to": "Test Group", "text": "Got it, POD coming shortly.", "question": null, "options": [], "reason": "The driver sent the BOL.",
     "answer": null, "result": null, "createdAt": "2026-11-10 18:31:18", "resolvedAt": null}],
   "summary": ""},
  {"runId": 7, "job": "job2", "jobName": "Job 2 - Datatruck", "at": "2026-11-10 18:27:40", "telegramMessageIds": [129446],
   "messageIds": [135733968896], "status": "running", "working": true, "decisions": [], "actions": [], "summary": ""}
 ]}
""".trimIndent()

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w390dp-h1400dp-xxhdpi")
class BrainPanelTest {
    @get:Rule
    val rule = createComposeRule()

    @Test fun readsTheServersPanel() {
        val panel = parseBrainPanel(PANEL)
        assertTrue(panel.active)
        assertEquals("Job 2 - Datatruck", panel.pausedJobs.single().name)
        assertEquals(listOf(13L, 6L, 7L), panel.items.map { it.runId })
        val question = panel.items[0].actions.single()
        assertTrue(question.isQuestion && question.isOpen)
        assertEquals(null, question.to)
        assertEquals(listOf("Say yes", "Say no"), question.options)
        assertEquals("Got it, POD coming shortly.", panel.items[1].actions.single().text)
        assertEquals(listOf(129446L shl 20), panel.items[2].messageIds)
        assertEquals(BrainMark.Working, panel.marks()[129446L shl 20])
        assertEquals(BrainMark.Waiting, panel.marks()[101L shl 20])
    }

    @Test fun messagesBrainHasNotStartedOnShowAsWorking() {
        val panel = parseBrainPanel("""{"active": true, "jobs": [], "items": [], "waiting": [${130000L shl 20}]}""")
        assertTrue(panel.busy)
        assertTrue(panel.isWaiting(listOf(130000L shl 20)))
        assertEquals(BrainMark.Working, panel.marks()[130000L shl 20])
        assertTrue(!parseBrainPanel(PANEL.replace("\"working\": true", "\"working\": false")).busy)
    }

    @Test fun aChatWithSendingOffShowsWhatBrainWouldHaveSent() {
        assertTrue(parseBrainPanel(PANEL).sending)
        val off = parseBrainPanel(PANEL.replace("\"active\": true,", "\"active\": true, \"sending\": false,")
            .replace("\"status\": \"open\", \"statusText\": \"Waiting for you\",\n     \"to\": \"Test Group\"",
                "\"status\": \"not_sent\", \"statusText\": \"Not sent\",\n     \"to\": \"Test Group\""))
        assertTrue(!off.sending)
        val draft = off.items[1].actions.single()
        assertTrue(draft.isUnsent && !draft.isOpen)
        assertEquals(BrainMark.Done, off.marks()[101L shl 20])
    }

    @Test fun brainTimesAreLocal() {
        assertEquals("", brainTime("not a time"))
        assertTrue(brainTime("2026-11-10 18:31:18").endsWith("18:31"))
    }

    private fun shot(mode: ThemeMode, name: String, selected: List<Long>?, json: String = PANEL) {
        val panel = parseBrainPanel(json)
        rule.setContent {
            FoxyTheme(mode) {
                Box(Modifier.background(Foxy.colors.surface).padding(top = 16.dp)) {
                    BrainPanelContent(
                        panel = panel,
                        error = null,
                        selectedIds = selected,
                        preview = selected?.let { BrainMessagePreview("Driver", "18:25", "BOL attached") },
                        onShowAll = {},
                        onJump = {},
                        onDecide = { _, _, _, _ -> },
                    )
                }
            }
        }
        rule.onRoot().captureRoboImage("build/shots/$name.png")
    }

    @Test fun sheetForAMessageDark() = shot(ThemeMode.Dark, "brain_message_dark", listOf(101L shl 20))
    @Test fun sheetForTheChatLight() = shot(ThemeMode.Light, "brain_chat_light", null)
    @Test fun sheetWithSendingOff() = shot(ThemeMode.Light, "brain_sending_off", listOf(101L shl 20),
        PANEL.replace("\"active\": true,", "\"active\": true, \"sending\": false,")
            .replace("\"status\": \"open\", \"statusText\": \"Waiting for you\",\n     \"to\": \"Test Group\"",
                "\"status\": \"not_sent\", \"statusText\": \"Not sent\",\n     \"to\": \"Test Group\""))
}
