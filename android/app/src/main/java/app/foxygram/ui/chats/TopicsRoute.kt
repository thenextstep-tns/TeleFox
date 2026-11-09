package app.foxygram.ui.chats

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.foxygram.model.TopicItem
import app.foxygram.td.ChatCommands
import app.foxygram.td.Telegram
import app.foxygram.ui.Route
import app.foxygram.ui.cases.EmptyNote
import app.foxygram.ui.cases.ScreenBar
import app.foxygram.ui.common.CountBadge
import app.foxygram.ui.common.listTime
import app.foxygram.ui.theme.Foxy
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.debounce

private const val TOPICS_DEBOUNCE_MS = 300L

/** A group with topics opens here first, the way Telegram shows them. */
@OptIn(FlowPreview::class)
@Composable
fun TopicsRoute(telegram: Telegram, chatId: Long, title: String, onBack: () -> Unit, navigate: (Route) -> Unit) {
    val colors = Foxy.colors
    val commands = remember { ChatCommands(telegram) }
    var topics by remember { mutableStateOf<List<TopicItem>?>(null) }
    var failed by remember { mutableStateOf(false) }

    DisposableEffect(chatId) {
        telegram.watchTopics(chatId)
        onDispose { telegram.unwatchTopics(chatId) }
    }
    LaunchedEffect(chatId) {
        telegram.topicsTick.debounce(TOPICS_DEBOUNCE_MS).collectLatest {
            runCatching { commands.forumTopics(chatId) }
                .onSuccess { loaded ->
                    topics = loaded
                    failed = false
                }
                .onFailure { error ->
                    if (error !is CancellationException) failed = topics == null
                }
        }
    }

    Column(Modifier.fillMaxSize().background(colors.background)) {
        ScreenBar(title, onBack)
        val list = topics
        when {
            failed -> EmptyNote("Не удалось загрузить темы.")
            list == null -> Unit
            else -> LazyColumn(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.navigationBars)) {
                item(key = "all") {
                    Text(
                        "Все сообщения", color = colors.accent, fontSize = 16.sp,
                        modifier = Modifier.fillMaxWidth().clickable { navigate(Route.Chat(chatId)) }.padding(horizontal = 16.dp, vertical = 14.dp),
                    )
                }
                items(list, key = { it.id }) { topic ->
                    TopicRow(topic) { navigate(Route.Chat(chatId, topic.id, topic.title)) }
                }
            }
        }
    }
}

@Composable
private fun TopicRow(topic: TopicItem, onClick: () -> Unit) {
    val colors = Foxy.colors
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(40.dp).clip(CircleShape).background(Color(topic.color)), contentAlignment = Alignment.Center) {
            Text(topic.title.take(1).uppercase(), color = Color.White, fontSize = 17.sp, fontWeight = FontWeight.Medium)
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(topic.title, color = colors.text, fontSize = 16.sp, fontWeight = FontWeight.Medium, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                Text(listTime(topic.date), color = colors.textSecondary, fontSize = 12.sp, modifier = Modifier.padding(start = 8.dp))
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(topic.preview, color = colors.textSecondary, fontSize = 14.sp, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                if (topic.unread > 0) {
                    Spacer(Modifier.width(8.dp))
                    CountBadge(topic.unread, if (topic.mentions > 0) colors.accent else colors.mutedBadge, fontSize = 12.sp)
                }
            }
        }
    }
}
