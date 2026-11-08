package app.foxygram.ui.chats

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.VolumeOff
import androidx.compose.material.icons.filled.AccessTime
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.DoneAll
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.PushPin
import androidx.compose.material.icons.filled.Verified
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.foxygram.model.ChatItem
import app.foxygram.model.SendState
import app.foxygram.ui.common.Avatar
import app.foxygram.ui.common.CountBadge
import app.foxygram.ui.common.LabelPill
import app.foxygram.ui.common.TelegramImage
import app.foxygram.ui.common.listTime
import app.foxygram.ui.theme.Foxy

private val RowHeight = 76.dp
private val AvatarSize = 56.dp
private val TextInset = 12.dp + AvatarSize + 12.dp

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun ChatRow(chat: ChatItem, onClick: () -> Unit, onLongClick: () -> Unit, modifier: Modifier = Modifier) {
    val colors = Foxy.colors
    Box(modifier.fillMaxWidth().height(RowHeight).combinedClickable(onClick = onClick, onLongClick = onLongClick)) {
        Row(Modifier.fillMaxWidth().height(RowHeight), verticalAlignment = Alignment.CenterVertically) {
            Spacer(Modifier.width(12.dp))
            Avatar(chat.title, chat.photo, chat.colorIndex, AvatarSize, kind = chat.kind)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f).padding(end = 12.dp), verticalArrangement = Arrangement.Center) {
                TitleLine(chat)
                Spacer(Modifier.height(3.dp))
                PreviewLine(chat)
            }
        }
        HorizontalDivider(Modifier.align(Alignment.BottomStart).padding(start = TextInset), thickness = 0.5.dp, color = colors.border)
    }
}

@Composable
private fun TitleLine(chat: ChatItem) {
    val colors = Foxy.colors
    Row(verticalAlignment = Alignment.CenterVertically) {
        Row(Modifier.weight(1f), verticalAlignment = Alignment.CenterVertically) {
            Text(
                chat.title,
                color = colors.text,
                fontSize = 16.5.sp,
                fontWeight = FontWeight.Medium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f, fill = false),
            )
            if (chat.verified) {
                Spacer(Modifier.width(3.dp))
                Icon(Icons.Filled.Verified, null, tint = colors.accent, modifier = Modifier.size(15.dp))
            }
            if (chat.muted) {
                Spacer(Modifier.width(3.dp))
                Icon(Icons.AutoMirrored.Filled.VolumeOff, null, tint = colors.textSecondary, modifier = Modifier.size(14.dp))
            }
        }
        Spacer(Modifier.width(6.dp))
        StatusIcon(chat.status)
        Spacer(Modifier.width(3.dp))
        Text(listTime(chat.date), color = colors.textSecondary, fontSize = 13.sp, maxLines = 1)
    }
}

@Composable
private fun StatusIcon(status: SendState) {
    val colors = Foxy.colors
    when (status) {
        SendState.Read -> Icon(Icons.Filled.DoneAll, null, tint = colors.accent, modifier = Modifier.size(16.dp))
        SendState.Sent -> Icon(Icons.Filled.Check, null, tint = colors.accent, modifier = Modifier.size(16.dp))
        SendState.Sending -> Icon(Icons.Filled.AccessTime, null, tint = colors.textSecondary, modifier = Modifier.size(14.dp))
        SendState.Failed -> Icon(Icons.Filled.ErrorOutline, null, tint = colors.danger, modifier = Modifier.size(16.dp))
        SendState.None -> Unit
    }
}

@Composable
private fun PreviewLine(chat: ChatItem) {
    val colors = Foxy.colors
    val label = chat.label
    Row(verticalAlignment = Alignment.CenterVertically) {
        if (label != null && label.needsReply) {
            Box(Modifier.size(8.dp).clip(CircleShape).background(if (label.urgent) colors.danger else colors.accent))
            Spacer(Modifier.width(5.dp))
        }
        if (label?.projectName != null) {
            LabelPill(label.projectName, label.projectColor?.let { Color(it) } ?: colors.accent)
            Spacer(Modifier.width(5.dp))
        }
        chat.previewThumb?.let {
            TelegramImage(it, Modifier.size(18.dp).clip(RoundedCornerShape(3.dp)), priority = 1)
            Spacer(Modifier.width(4.dp))
        }
        Text(
            previewText(chat, colors.text, colors.accent, colors.danger),
            color = colors.textSecondary,
            fontSize = 15.sp,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f),
        )
        Trailing(chat)
    }
}

private fun previewText(chat: ChatItem, senderColor: Color, labelColor: Color, draftColor: Color) = buildAnnotatedString {
    when {
        chat.typing != null -> withStyle(SpanStyle(color = labelColor)) { append(chat.typing) }
        chat.draft != null -> {
            withStyle(SpanStyle(color = draftColor)) { append("Черновик: ") }
            append(chat.draft)
        }
        else -> {
            if (chat.senderPrefix != null) {
                withStyle(SpanStyle(color = senderColor)) { append(chat.senderPrefix) }
                withStyle(SpanStyle(color = senderColor)) { append(": ") }
            }
            if (chat.previewIsLabel) withStyle(SpanStyle(color = labelColor)) { append(chat.preview) } else append(chat.preview)
        }
    }
}

@Composable
private fun Trailing(chat: ChatItem) {
    val colors = Foxy.colors
    val badge = if (chat.muted) colors.mutedBadge else colors.accent
    if (chat.reactions > 0) {
        Spacer(Modifier.width(6.dp))
        Box(Modifier.size(22.dp).clip(CircleShape).background(colors.danger), contentAlignment = Alignment.Center) {
            Icon(Icons.Filled.Favorite, null, tint = Color.White, modifier = Modifier.size(12.dp))
        }
    }
    if (chat.mentions > 0) {
        Spacer(Modifier.width(6.dp))
        Box(Modifier.size(22.dp).clip(CircleShape).background(colors.accent), contentAlignment = Alignment.Center) {
            Text("@", color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Medium)
        }
    }
    if (chat.unread > 0) {
        Spacer(Modifier.width(6.dp))
        CountBadge(chat.unread, badge)
    } else if (chat.pinned) {
        Spacer(Modifier.width(6.dp))
        Icon(Icons.Filled.PushPin, null, tint = colors.textSecondary, modifier = Modifier.size(18.dp))
    }
}
