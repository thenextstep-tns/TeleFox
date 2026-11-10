package app.foxygram

import app.foxygram.data.BrainAction
import app.foxygram.data.BrainMark
import app.foxygram.data.BrainPanel
import app.foxygram.data.BrainPanelJob
import app.foxygram.data.BrainRun
import app.foxygram.model.ChatKind
import app.foxygram.model.FeedRow
import app.foxygram.model.ImageRef
import app.foxygram.model.MessageBody
import app.foxygram.model.MessageItem
import app.foxygram.model.RichText
import app.foxygram.model.Sender
import app.foxygram.model.buildFeed
import app.foxygram.notify.AlertFacts
import app.foxygram.notify.AlertMode
import app.foxygram.notify.loudestMode
import app.foxygram.notify.shouldAlert
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LogicTest {
    private val base = AlertFacts(
        outgoing = false, pending = false, isService = false, ageSeconds = 2,
        muted = false, mentionsMe = false, mentionAlertsOff = false, chatOnScreen = false,
    )

    @Test fun normalMessageAlerts() = assertTrue(shouldAlert(base))
    @Test fun ownMessageNeverAlerts() = assertFalse(shouldAlert(base.copy(outgoing = true)))
    @Test fun openChatDoesNotAlert() = assertFalse(shouldAlert(base.copy(chatOnScreen = true)))
    @Test fun serviceLinesDoNotAlert() = assertFalse(shouldAlert(base.copy(isService = true)))
    @Test fun mutedChatStaysQuiet() = assertFalse(shouldAlert(base.copy(muted = true)))
    @Test fun mentionBreaksMute() = assertTrue(shouldAlert(base.copy(muted = true, mentionsMe = true)))
    @Test fun mentionRespectsItsOwnSetting() = assertFalse(shouldAlert(base.copy(muted = true, mentionsMe = true, mentionAlertsOff = true)))
    @Test fun catchUpAfterSleepIsSilent() = assertFalse(shouldAlert(base.copy(ageSeconds = 3600)))
    @Test fun folderOffSilencesEvenMentions() = assertFalse(shouldAlert(base.copy(mentionsMe = true, folderMode = AlertMode.Off)))
    @Test fun mentionsFolderSkipsPlainMessages() = assertFalse(shouldAlert(base.copy(folderMode = AlertMode.Mentions)))
    @Test fun mentionsFolderAlertsOnMention() = assertTrue(shouldAlert(base.copy(mentionsMe = true, folderMode = AlertMode.Mentions)))
    @Test fun mentionsFolderRespectsChatSetting() = assertFalse(shouldAlert(base.copy(mentionsMe = true, mentionAlertsOff = true, folderMode = AlertMode.Mentions)))
    @Test fun loudestFolderWins() = assertEquals(AlertMode.All, loudestMode(listOf(AlertMode.Off, AlertMode.All, AlertMode.Mentions)))
    @Test fun quietFoldersStayQuiet() = assertEquals(AlertMode.Mentions, loudestMode(listOf(AlertMode.Off, AlertMode.Mentions)))
    @Test fun noFoldersMeansNormalAlerts() = assertEquals(AlertMode.All, loudestMode(emptyList()))

    private val day = 1_700_000_000
    private val alice = Sender(1, "Alice")
    private val bob = Sender(2, "Bob")

    private fun message(id: Long, sender: Sender, date: Int, outgoing: Boolean = false, album: Long = 0, body: MessageBody = MessageBody.Text(RichText("x"))) =
        MessageItem(id, 9, date, outgoing, sender, body, albumId = album)

    private fun rows(vararg items: MessageItem) = buildFeed(items.toList(), ChatKind.Group, null).filterIsInstance<FeedRow.Message>()

    @Test fun sameSenderJoinsAGroup() {
        val feed = rows(message(2, alice, day + 30), message(1, alice, day))
        assertFalse(feed[0].startsGroup)
        assertTrue(feed[0].endsGroup)
        assertTrue(feed[1].startsGroup)
        assertFalse(feed[1].endsGroup)
    }

    @Test fun longPauseSplitsAGroup() {
        val feed = rows(message(2, alice, day + 3600), message(1, alice, day))
        assertTrue(feed[0].startsGroup)
        assertTrue(feed[1].endsGroup)
    }

    @Test fun differentSendersDoNotJoin() {
        val feed = rows(message(2, bob, day + 10), message(1, alice, day))
        assertTrue(feed[0].showSenderName && feed[1].showSenderName)
        assertTrue(feed[0].showAvatar && feed[1].showAvatar)
    }

    @Test fun onlyTheLastMessageOfAGroupShowsAnAvatar() {
        val feed = rows(message(2, alice, day + 10), message(1, alice, day))
        assertTrue(feed[0].showAvatar)
        assertFalse(feed[1].showAvatar)
    }

    @Test fun albumMembersMergeOldestFirst() {
        val a = MessageBody.Photo(ImageRef(1))
        val b = MessageBody.Photo(ImageRef(2))
        val feed = rows(message(2, alice, day, album = 77, body = b), message(1, alice, day, album = 77, body = a))
        assertEquals(1, feed.size)
        assertEquals(listOf<Long>(1, 2), feed[0].item.groupIds)
        assertEquals(listOf<MessageBody>(a, b), (feed[0].item.body as MessageBody.Album).items)
    }

    @Test fun filesSentTogetherStayOneMessageEach() {
        // Two permits sent as one group, as a driver did in "Truck 1442": both must show, each with its name.
        val ks = MessageBody.Document(11, "KS permit.pdf", 43041, "application/pdf", null, RichText.Empty)
        val mo = MessageBody.Document(12, "MO permit.pdf", 123977, "application/pdf", null, RichText.Empty)
        val feed = rows(message(2, alice, day, album = 88, body = mo), message(1, alice, day, album = 88, body = ks))
        assertEquals(2, feed.size)
        assertEquals(listOf<MessageBody>(mo, ks), feed.map { it.item.body })
        assertTrue(feed.none { it.item.body is MessageBody.Album })
    }

    @Test fun dayChangeAddsADateRow() {
        val feed = buildFeed(listOf(message(2, alice, day + 90000), message(1, alice, day)), ChatKind.Group, null)
        assertEquals(2, feed.count { it is FeedRow.Date })
    }

    @Test fun unreadMarkerSitsJustAboveTheFirstUnread() {
        val feed = buildFeed(listOf(message(2, alice, day + 10), message(1, alice, day)), ChatKind.Group, 2)
        assertTrue(feed[1] is FeedRow.UnreadMarker)
    }

    private fun brainRun(id: Long, ids: List<Long>, working: Boolean = false, status: String = "done", actionStatus: String? = null) = BrainRun(
        runId = id, jobName = "Job 2", at = "2026-11-10 18:31:18", messageIds = ids, status = status, working = working,
        decisions = listOf("decided"), summary = "",
        actions = listOfNotNull(actionStatus?.let {
            BrainAction(id * 10, "approval", "telegram.send", it, "Test Group", "Got it", null, emptyList(), null, null, null)
        }),
    )

    @Test fun brainMarksEachAnalysedMessageWithItsMostPressingState() {
        val panel = BrainPanel(true, listOf(BrainPanelJob("job2", "Job 2", false)), listOf(
            brainRun(1, listOf(101L shl 20, 102L shl 20), actionStatus = "executed"),
            brainRun(2, listOf(102L shl 20), actionStatus = "open"),
            brainRun(3, listOf(103L shl 20), working = true),
            brainRun(4, listOf(104L shl 20), status = "error"),
        ))
        val marks = panel.marks()
        assertEquals(BrainMark.Done, marks[101L shl 20])
        assertEquals(BrainMark.Waiting, marks[102L shl 20])
        assertEquals(BrainMark.Working, marks[103L shl 20])
        assertEquals(BrainMark.Failed, marks[104L shl 20])
        assertEquals(null, marks[105L shl 20])
    }

    @Test fun brainFindsEveryRunAboutAMessageOrAlbum() {
        val panel = BrainPanel(true, emptyList(), listOf(brainRun(7, listOf(129446L shl 20)), brainRun(8, listOf(5L shl 20, 6L shl 20))))
        assertEquals(listOf(7L), panel.runsFor(listOf(129446L shl 20)).map { it.runId })
        assertEquals(listOf(8L), panel.runsFor(listOf(6L shl 20, 9L)).map { it.runId })
        assertTrue(panel.runsFor(listOf(129446L)).isEmpty())
    }
}
