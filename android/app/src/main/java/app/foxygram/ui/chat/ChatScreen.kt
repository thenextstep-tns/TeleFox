package app.foxygram.ui.chat

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.foxygram.model.ChatItem
import app.foxygram.model.ChatKind
import app.foxygram.model.FeedRow
import app.foxygram.ui.common.Avatar
import app.foxygram.ui.common.CountBadge
import app.foxygram.ui.common.LabelPill
import app.foxygram.ui.theme.Foxy
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.launch

private const val LOAD_MORE_MARGIN = 20

data class ChatHeaderState(val chat: ChatItem, val subtitle: String)

@Composable
fun ChatScreen(
    header: ChatHeaderState,
    feed: List<FeedRow>,
    listState: LazyListState,
    actions: MessageActions,
    onBack: () -> Unit,
    onHeader: () -> Unit,
    onMenu: () -> Unit,
    onLoadOlder: () -> Unit,
    onLoadNewer: () -> Unit,
    onVisibleMessages: (List<Long>) -> Unit,
    onScrollToBottom: () -> Unit,
    composer: @Composable () -> Unit,
    modifier: Modifier = Modifier,
    onBrain: (() -> Unit)? = null,
    /** How many things wait for the owner in this chat (Brain's suggestions and questions). */
    brainWaiting: Int = 0,
) {
    val colors = Foxy.colors
    val isGroup = header.chat.kind == ChatKind.Group
    val scope = rememberCoroutineScope()
    Column(modifier.fillMaxSize().background(colors.background).windowInsetsPadding(WindowInsets.navigationBars).imePadding()) {
        Header(header, onBack, onHeader, onMenu, onBrain, brainWaiting)
        Box(Modifier.weight(1f).fillMaxWidth()) {
            LazyColumn(
                Modifier.fillMaxSize(),
                state = listState,
                reverseLayout = true,
                contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 6.dp),
            ) {
                items(feed, key = { it.key }, contentType = { it::class }) { row ->
                    when (row) {
                        is FeedRow.Date -> DatePill(row.text)
                        FeedRow.UnreadMarker -> UnreadLine()
                        is FeedRow.Message -> MessageRow(row, isGroup, actions)
                    }
                }
            }
            val showDown by remember { derivedStateOf { listState.firstVisibleItemIndex > 2 } }
            if (showDown) {
                Box(
                    Modifier.align(Alignment.BottomEnd).padding(12.dp).size(44.dp).clip(CircleShape).background(colors.surfaceHigh)
                        .clickable {
                            onScrollToBottom()
                            scope.launch { listState.scrollToItem(0) }
                        },
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(Icons.Filled.KeyboardArrowDown, "Вниз", tint = colors.text)
                    if (header.chat.unread > 0) {
                        CountBadge(header.chat.unread, colors.accent, Modifier.align(Alignment.TopCenter).padding(bottom = 30.dp), 12.sp)
                    }
                }
            }
        }
        composer()
    }

    val nearOlder by remember(feed.size) {
        derivedStateOf {
            val last = listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0
            feed.isNotEmpty() && last >= feed.size - LOAD_MORE_MARGIN
        }
    }
    LaunchedEffect(listState, feed.size) {
        snapshotFlow { nearOlder }.distinctUntilChanged().filter { it }.collect { onLoadOlder() }
    }
    val nearNewer by remember(feed.size) { derivedStateOf { listState.firstVisibleItemIndex <= LOAD_MORE_MARGIN } }
    LaunchedEffect(listState, feed.size) {
        snapshotFlow { nearNewer }.distinctUntilChanged().filter { it }.collect { onLoadNewer() }
    }
    LaunchedEffect(listState, feed) {
        snapshotFlow { listState.layoutInfo.visibleItemsInfo.map { it.index } }
            .distinctUntilChanged()
            .collect { indices ->
                val ids = indices.mapNotNull { index -> (feed.getOrNull(index) as? FeedRow.Message)?.item }
                    .flatMap { item -> item.groupIds.ifEmpty { listOf(item.id) } }
                if (ids.isNotEmpty()) onVisibleMessages(ids)
            }
    }
}

@Composable
private fun Header(header: ChatHeaderState, onBack: () -> Unit, onHeader: () -> Unit, onMenu: () -> Unit, onBrain: (() -> Unit)?, brainWaiting: Int = 0) {
    val colors = Foxy.colors
    val chat = header.chat
    Column(Modifier.fillMaxWidth().background(colors.surface).windowInsetsPadding(WindowInsets.statusBars)) {
        Row(Modifier.fillMaxWidth().height(56.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Назад", tint = colors.text) }
            Row(Modifier.weight(1f).clickable(onClick = onHeader), verticalAlignment = Alignment.CenterVertically) {
                Avatar(chat.title, chat.photo, chat.colorIndex, 40.dp, kind = chat.kind)
                Spacer(Modifier.width(10.dp))
                Column {
                    Text(chat.title, color = colors.text, fontSize = 17.sp, fontWeight = FontWeight.Medium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Text(header.subtitle, color = colors.textSecondary, fontSize = 13.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
            }
            if (onBrain != null) {
                Box {
                    IconButton(onBrain) { Icon(Icons.Filled.SmartToy, "Brain", tint = colors.accent) }
                    if (brainWaiting > 0) CountBadge(brainWaiting, colors.warning, Modifier.align(Alignment.TopEnd).padding(top = 4.dp, end = 2.dp), 11.sp)
                }
            }
            IconButton(onMenu) { Icon(Icons.Filled.MoreVert, "Ещё", tint = colors.text) }
        }
        // Brain's suggestions and questions for this chat, pinned where they can't be missed.
        if (onBrain != null && brainWaiting > 0) {
            Row(
                Modifier.fillMaxWidth().background(colors.warning.copy(alpha = 0.12f)).clickable(onClick = onBrain).padding(horizontal = 16.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(Icons.Filled.SmartToy, null, tint = colors.warning, modifier = Modifier.size(16.dp))
                Spacer(Modifier.width(8.dp))
                Text(if (brainWaiting == 1) "Brain suggests something · tap to review" else "Brain suggests $brainWaiting things · tap to review",
                    color = colors.warning, fontSize = 14.sp, fontWeight = FontWeight.Medium, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
        val caseTitle = chat.label?.caseTitle
        if (caseTitle != null) {
            Row(
                Modifier.fillMaxWidth().padding(start = 12.dp, end = 12.dp, bottom = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                LabelPill("Дело", colors.accent)
                Spacer(Modifier.width(6.dp))
                Text(caseTitle, color = colors.text, fontSize = 13.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
    }
}
