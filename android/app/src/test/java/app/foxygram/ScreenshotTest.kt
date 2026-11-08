package app.foxygram

import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.text.input.TextFieldValue
import app.foxygram.model.ChatKind
import app.foxygram.model.MessageBody
import app.foxygram.model.MessageItem
import app.foxygram.model.buildFeed
import app.foxygram.ui.chat.ChatHeaderState
import app.foxygram.ui.chat.ChatScreen
import app.foxygram.ui.chat.Composer
import app.foxygram.ui.chat.MessageActions
import app.foxygram.ui.chats.ChatListScreen
import app.foxygram.ui.theme.FoxyTheme
import app.foxygram.ui.theme.ThemeMode
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

private object NoActions : MessageActions {
    override fun onTap(item: MessageItem) = Unit
    override fun onLongPress(item: MessageItem) = Unit
    override fun onReply(item: MessageItem) = Unit
    override fun onJumpTo(messageId: Long) = Unit
    override fun onReaction(item: MessageItem, emoji: String) = Unit
    override fun onOpenMedia(item: MessageItem, body: MessageBody) = Unit
    override fun onOpenFile(fileId: Int, name: String, mime: String) = Unit
    override fun onLink(url: String) = Unit
    override fun onVote(item: MessageItem, optionIndex: Int) = Unit
    override fun onSender(item: MessageItem) = Unit
}

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w390dp-h844dp-xxhdpi")
class ScreenshotTest {
    @get:Rule
    val rule = createComposeRule()

    private fun chatList(mode: ThemeMode, name: String) {
        rule.setContent {
            FoxyTheme(mode) {
                ChatListScreen(DemoData.chats, DemoData.folders, 0, null, {}, {}, {}, {}, {}, {}, null)
            }
        }
        rule.onRoot().captureRoboImage("build/shots/$name.png")
    }

    private fun chat(mode: ThemeMode, name: String) {
        val feed = buildFeed(DemoData.messages, ChatKind.Group, null)
        rule.setContent {
            FoxyTheme(mode) {
                ChatScreen(
                    ChatHeaderState(DemoData.chats[1], "5 участников, 2 в сети"),
                    feed,
                    rememberLazyListState(),
                    NoActions,
                    {}, {}, {}, {}, {}, {}, {},
                    composer = { Composer(TextFieldValue(""), {}, null, null, {}, {}, {}, {}, {}) },
                )
            }
        }
        rule.onRoot().captureRoboImage("build/shots/$name.png")
    }

    @Test fun chatListDark() = chatList(ThemeMode.Dark, "chats_dark")
    @Test fun chatListLight() = chatList(ThemeMode.Light, "chats_light")
    @Test fun chatDark() = chat(ThemeMode.Dark, "chat_dark")
    @Test fun chatLight() = chat(ThemeMode.Light, "chat_light")
}
