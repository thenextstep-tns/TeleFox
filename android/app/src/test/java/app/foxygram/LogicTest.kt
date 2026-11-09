package app.foxygram

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

    @Test fun dayChangeAddsADateRow() {
        val feed = buildFeed(listOf(message(2, alice, day + 90000), message(1, alice, day)), ChatKind.Group, null)
        assertEquals(2, feed.count { it is FeedRow.Date })
    }

    @Test fun unreadMarkerSitsJustAboveTheFirstUnread() {
        val feed = buildFeed(listOf(message(2, alice, day + 10), message(1, alice, day)), ChatKind.Group, 2)
        assertTrue(feed[1] is FeedRow.UnreadMarker)
    }
}
