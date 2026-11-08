package app.foxygram.ui.chat

import androidx.compose.animation.core.Animatable
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Reply
import androidx.compose.material.icons.filled.AccessTime
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.DoneAll
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.foxygram.model.FeedRow
import app.foxygram.model.MessageBody
import app.foxygram.model.MessageItem
import app.foxygram.model.ReactionItem
import app.foxygram.model.ReplyInfo
import app.foxygram.model.SendState
import app.foxygram.ui.common.Avatar
import app.foxygram.ui.common.TelegramImage
import app.foxygram.ui.common.clockTime
import app.foxygram.ui.common.formatCount
import app.foxygram.ui.theme.Foxy
import app.foxygram.ui.theme.FoxyColors
import kotlinx.coroutines.launch
import kotlin.math.abs
import kotlin.math.roundToInt

private val AvatarSlot = 38.dp
private val SwipeThreshold = 64.dp

interface MessageActions {
    fun onTap(item: MessageItem)
    fun onLongPress(item: MessageItem)
    fun onReply(item: MessageItem)
    fun onJumpTo(messageId: Long)
    fun onReaction(item: MessageItem, emoji: String)
    fun onOpenMedia(item: MessageItem, body: MessageBody)
    fun onOpenFile(fileId: Int, name: String, mime: String)
    fun onLink(url: String)
    fun onVote(item: MessageItem, optionIndex: Int)
    fun onSender(item: MessageItem)
}

private fun FeedRow.Message.bubbleless(): Boolean = item.body is MessageBody.Sticker || item.body is MessageBody.Round

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun MessageRow(row: FeedRow.Message, isGroupChat: Boolean, actions: MessageActions) {
    val item = row.item
    val body = item.body
    if (body is MessageBody.Service) {
        ServiceLine(body.text)
        return
    }
    val density = LocalDensity.current
    val thresholdPx = with(density) { SwipeThreshold.toPx() }
    val swipe = remember { Animatable(0f) }
    val scope = rememberCoroutineScope()
    var dragged by remember { mutableFloatStateOf(0f) }
    val avatarWidth = if (isGroupChat && !item.outgoing) AvatarSlot + 4.dp else 0.dp
    val screenWidth = LocalConfiguration.current.screenWidthDp.dp
    val maxBubble = (screenWidth * if (item.outgoing) 0.82f else 0.86f) - avatarWidth

    Box(
        Modifier
            .fillMaxWidth()
            .padding(top = if (row.startsGroup) 6.dp else 2.dp)
            .pointerInput(item.id) {
                detectHorizontalDragGestures(
                    onDragStart = { dragged = 0f },
                    onDragEnd = {
                        if (abs(dragged) >= thresholdPx) actions.onReply(item)
                        dragged = 0f
                        scope.launch { swipe.animateTo(0f) }
                    },
                    onDragCancel = { scope.launch { swipe.animateTo(0f) } },
                    onHorizontalDrag = { _, amount ->
                        dragged = (dragged + amount).coerceIn(-thresholdPx * 1.3f, 0f)
                        scope.launch { swipe.snapTo(dragged) }
                    },
                )
            },
    ) {
        if (swipe.value < -4f) {
            Icon(
                Icons.AutoMirrored.Filled.Reply,
                null,
                tint = Foxy.colors.accent,
                modifier = Modifier.align(Alignment.CenterEnd).padding(end = 16.dp).size(22.dp),
            )
        }
        Row(
            Modifier.fillMaxWidth().offset { IntOffset(swipe.value.roundToInt(), 0) }.padding(horizontal = 8.dp),
            horizontalArrangement = if (item.outgoing) Arrangement.End else Arrangement.Start,
            verticalAlignment = Alignment.Bottom,
        ) {
            if (isGroupChat && !item.outgoing) {
                if (row.showAvatar && item.sender != null) {
                    Avatar(
                        item.sender.name, item.sender.photo, item.sender.colorIndex, AvatarSlot,
                        Modifier.clickable { actions.onSender(item) },
                    )
                } else {
                    Spacer(Modifier.width(AvatarSlot))
                }
                Spacer(Modifier.width(4.dp))
            }
            Column(horizontalAlignment = if (item.outgoing) Alignment.End else Alignment.Start) {
                if (row.bubbleless()) BareMessage(row, maxBubble, actions) else Bubble(row, maxBubble, actions)
                if (item.reactions.isNotEmpty() && row.bubbleless()) {
                    Reactions(item, actions, Modifier.padding(top = 4.dp))
                }
            }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
private fun Modifier.messageClicks(item: MessageItem, actions: MessageActions): Modifier =
    combinedClickable(
        interactionSource = null,
        indication = null,
        onClick = { actions.onTap(item) },
        onLongClick = { actions.onLongPress(item) },
    )

@Composable
private fun Bubble(row: FeedRow.Message, maxWidth: Dp, actions: MessageActions) {
    val item = row.item
    val colors = Foxy.colors
    val background = if (item.outgoing) colors.bubbleOut else colors.bubbleIn
    val shape = remember(item.outgoing, row.startsGroup, row.endsGroup) {
        BubbleShape(item.outgoing, row.startsGroup, row.endsGroup)
    }
    val inset = if (row.endsGroup) 7.dp else 0.dp
    val tailPadding = if (item.outgoing) Modifier.padding(end = inset) else Modifier.padding(start = inset)
    val spacing = if (row.endsGroup) 0.dp else 7.dp
    val outerSpacing = if (item.outgoing) Modifier.padding(end = spacing) else Modifier.padding(start = spacing)
    Box(
        outerSpacing
            .widthIn(max = maxWidth)
            .clip(shape)
            .background(background)
            .messageClicks(item, actions),
    ) {
        Column(tailPadding.width(IntrinsicSize.Max)) {
            BubbleContent(row, maxWidth - 7.dp, actions)
        }
    }
}

@Composable
private fun BubbleContent(row: FeedRow.Message, width: Dp, actions: MessageActions) {
    val item = row.item
    val colors = Foxy.colors
    val textColor = colors.text
    val meta = metaColor(colors, item)
    val body = item.body
    val hasHeader = row.showSenderName || item.forwardFrom != null || item.reply != null
    val caption = when (body) {
        is MessageBody.Text -> body.text
        else -> body.caption
    }
    val visualBody = body is MessageBody.Photo || body is MessageBody.Video || body is MessageBody.Album

    if (hasHeader) {
        Column(Modifier.padding(start = 10.dp, end = 10.dp, top = 6.dp, bottom = if (visualBody) 5.dp else 0.dp)) {
            if (row.showSenderName && item.sender != null) {
                val nameColor = colors.name[Math.floorMod(item.sender.colorIndex, colors.name.size)]
                Text(
                    item.sender.name,
                    color = nameColor,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            item.forwardFrom?.let {
                Text(
                    "Переслано от $it",
                    color = colors.accent,
                    fontSize = 13.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            item.reply?.let { ReplyQuote(it, item.outgoing, Modifier.padding(top = 3.dp, bottom = 3.dp)) { actions.onJumpTo(it.messageId) } }
        }
    }

    if (visualBody) {
        VisualMedia(item, body, width, actions, overlayMeta = caption.isBlank && item.reactions.isEmpty())
    }
    when (body) {
        is MessageBody.Voice -> Inset { VoiceBody(body, item.outgoing) }
        is MessageBody.Audio -> Inset { AudioBody(body, item.outgoing) }
        is MessageBody.Document -> Inset { DocumentBody(body, item.outgoing, actions) }
        is MessageBody.Poll -> Inset { PollBody(item, body, actions) }
        is MessageBody.Location -> Inset { LocationBody(body, actions) }
        is MessageBody.Contact -> Inset { ContactBody(body) }
        is MessageBody.Call -> Inset { CallBody(item, body) }
        MessageBody.Unsupported -> Inset { Text("Этот тип сообщения пока не поддерживается", color = colors.textSecondary, fontSize = 15.sp) }
        else -> Unit
    }

    val showText = !caption.isBlank
    val metaWidth = estimateMetaWidth(item)
    Box(Modifier.fillMaxWidth().widthIn(min = 72.dp)) {
        Column {
            if (showText) {
                RichTextView(
                    caption,
                    textColor,
                    if (item.outgoing) colors.linkOut else colors.link,
                    if (item.reactions.isEmpty() && (body !is MessageBody.Text || body.web == null)) metaWidth else 0.sp,
                    { actions.onLink(it) },
                    Modifier.padding(start = 10.dp, end = 10.dp, top = if (hasHeader && !visualBody) 2.dp else 6.dp, bottom = 6.dp),
                )
            }
            if (body is MessageBody.Text && body.web != null) {
                WebCard(body.web, item.outgoing, actions, Modifier.padding(start = 10.dp, end = 10.dp, bottom = 22.dp))
            }
            if (item.reactions.isNotEmpty()) {
                Reactions(item, actions, Modifier.padding(start = 8.dp, end = 8.dp, bottom = 22.dp))
            } else if (!showText && !visualBody && body !is MessageBody.Text) {
                Spacer(Modifier.height(16.dp))
            }
        }
        if (!(visualBody && caption.isBlank && item.reactions.isEmpty())) {
            Meta(item, meta, Modifier.align(Alignment.BottomEnd).padding(end = 8.dp, bottom = 4.dp))
        }
    }
}

@Composable
private fun Inset(content: @Composable () -> Unit) {
    Box(Modifier.padding(start = 10.dp, end = 10.dp, top = 8.dp)) { content() }
}

private fun metaColor(colors: FoxyColors, item: MessageItem): Color = if (item.outgoing) colors.bubbleOutMeta else colors.bubbleInMeta

private fun estimateMetaWidth(item: MessageItem): TextUnit {
    var width = 44f
    if (item.outgoing) width += 18f
    if (item.edited) width += 28f
    if (item.views > 0) width += 40f
    return width.sp
}

@Composable
fun Meta(item: MessageItem, color: Color, modifier: Modifier = Modifier) {
    Row(modifier, verticalAlignment = Alignment.CenterVertically) {
        if (item.views > 0) Text(formatCount(item.views) + "  ", color = color, fontSize = 12.sp)
        if (item.edited) Text("изм. ", color = color, fontSize = 12.sp)
        Text(clockTime(item.date), color = color, fontSize = 12.sp)
        if (item.outgoing) {
            Spacer(Modifier.width(3.dp))
            val tint = if (item.state == SendState.Read) Foxy.colors.accent else color
            when (item.state) {
                SendState.Read -> Icon(Icons.Filled.DoneAll, "Прочитано", tint = tint, modifier = Modifier.size(15.dp))
                SendState.Sent -> Icon(Icons.Filled.Check, "Отправлено", tint = tint, modifier = Modifier.size(15.dp))
                SendState.Sending -> Icon(Icons.Filled.AccessTime, "Отправляется", tint = tint, modifier = Modifier.size(13.dp))
                SendState.Failed -> Icon(Icons.Filled.ErrorOutline, "Ошибка", tint = Foxy.colors.danger, modifier = Modifier.size(15.dp))
                SendState.None -> Unit
            }
        }
    }
}

@Composable
private fun ReplyQuote(reply: ReplyInfo, outgoing: Boolean, modifier: Modifier = Modifier, onClick: () -> Unit) {
    val colors = Foxy.colors
    val accent = if (outgoing) colors.linkOut else colors.name[Math.floorMod(reply.colorIndex, colors.name.size)]
    Row(
        modifier
            .clip(RoundedCornerShape(5.dp))
            .background(accent.copy(alpha = 0.12f))
            .clickable(onClick = onClick)
            .height(IntrinsicSize.Min),
    ) {
        Box(Modifier.width(3.dp).fillMaxHeight().background(accent))
        reply.thumb?.let {
            TelegramImage(it, Modifier.padding(start = 5.dp, top = 4.dp, bottom = 4.dp).size(32.dp).clip(RoundedCornerShape(4.dp)), priority = 1)
        }
        Column(Modifier.padding(horizontal = 6.dp, vertical = 3.dp)) {
            Text(reply.senderName, color = accent, fontSize = 13.sp, fontWeight = FontWeight.Medium, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(reply.text, color = colors.text, fontSize = 13.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun Reactions(item: MessageItem, actions: MessageActions, modifier: Modifier = Modifier) {
    val colors = Foxy.colors
    FlowRow(modifier, horizontalArrangement = Arrangement.spacedBy(4.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        item.reactions.forEach { reaction: ReactionItem ->
            val background = if (reaction.chosen) colors.accent else colors.accentSoft
            val text = if (reaction.chosen) colors.onAccent else colors.text
            Row(
                Modifier
                    .clip(RoundedCornerShape(13.dp))
                    .background(background)
                    .clickable(remember { MutableInteractionSource() }, null) { actions.onReaction(item, reaction.emoji) }
                    .padding(horizontal = 8.dp, vertical = 3.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(reaction.emoji, fontSize = 14.sp)
                Spacer(Modifier.width(4.dp))
                Text(formatCount(reaction.count), color = text, fontSize = 13.sp)
            }
        }
    }
}

@Composable
fun ServiceLine(text: String) {
    val colors = Foxy.colors
    Box(Modifier.fillMaxWidth().padding(vertical = 6.dp, horizontal = 32.dp), contentAlignment = Alignment.Center) {
        Text(
            text,
            color = colors.onServicePill,
            fontSize = 13.sp,
            modifier = Modifier.clip(RoundedCornerShape(12.dp)).background(colors.servicePill).padding(horizontal = 10.dp, vertical = 3.dp),
        )
    }
}

@Composable
fun DatePill(text: String) = ServiceLine(text)

@Composable
fun UnreadLine() {
    val colors = Foxy.colors
    Box(Modifier.fillMaxWidth().padding(vertical = 6.dp).background(colors.surface).padding(vertical = 4.dp), contentAlignment = Alignment.Center) {
        Text("Непрочитанные сообщения", color = colors.accent, fontSize = 14.sp, fontWeight = FontWeight.Medium)
    }
}

@Composable
fun MetaPill(item: MessageItem, modifier: Modifier = Modifier) {
    Box(modifier.clip(CircleShape).background(Color(0x99000000)).padding(horizontal = 6.dp, vertical = 2.dp)) {
        Meta(item, Color.White)
    }
}
