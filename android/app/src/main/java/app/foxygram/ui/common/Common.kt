package app.foxygram.ui.common

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.foxygram.model.ChatKind
import app.foxygram.model.ImageRef
import app.foxygram.ui.theme.Foxy
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import java.util.Locale

@Composable
fun Avatar(
    title: String,
    photo: ImageRef?,
    colorIndex: Int,
    size: Dp,
    modifier: Modifier = Modifier,
    kind: ChatKind = ChatKind.Private,
) {
    val colors = Foxy.colors
    val background = colors.avatar[Math.floorMod(colorIndex, colors.avatar.size)]
    Box(
        modifier.size(size).clip(CircleShape).background(background),
        contentAlignment = Alignment.Center,
    ) {
        when {
            kind == ChatKind.Saved ->
                Icon(Icons.Filled.Bookmark, null, tint = Color.White, modifier = Modifier.size(size * 0.5f))
            else -> {
                Text(initials(title), color = Color.White, fontSize = (size.value * 0.36f).sp, fontWeight = FontWeight.Medium)
                if (photo != null) TelegramImage(photo, Modifier.fillMaxSize(), priority = 2)
            }
        }
    }
}

fun initials(title: String): String {
    val words = title.trim().split(Regex("\\s+")).filter { w -> w.firstOrNull()?.isLetterOrDigit() == true }
    return when (words.size) {
        0 -> title.take(1).uppercase()
        1 -> words[0].take(1).uppercase()
        else -> (words[0].take(1) + words[1].take(1)).uppercase()
    }
}

@Composable
fun CountBadge(count: Int, background: Color, modifier: Modifier = Modifier, fontSize: TextUnit = 13.sp) {
    Box(
        modifier
            .height(22.dp)
            .widthIn(min = 22.dp)
            .clip(RoundedCornerShape(11.dp))
            .background(background)
            .padding(horizontal = 6.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(formatCount(count), color = Color.White, fontSize = fontSize, fontWeight = FontWeight.Medium, maxLines = 1)
    }
}

fun formatCount(count: Int): String = when {
    count >= 1_000_000 -> "${count / 1_000_000}M"
    count >= 10_000 -> "${count / 1000}K"
    else -> count.toString()
}

@Composable
fun LabelPill(text: String, color: Color, modifier: Modifier = Modifier) {
    Row(
        modifier
            .clip(RoundedCornerShape(6.dp))
            .background(color.copy(alpha = 0.16f))
            .padding(horizontal = 6.dp, vertical = 1.dp),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(text, color = color, fontSize = 11.sp, fontWeight = FontWeight.Medium, maxLines = 1)
    }
}

private val zone: ZoneId get() = ZoneId.systemDefault()
private val ru = Locale.forLanguageTag("ru")
private val clockFormat = DateTimeFormatter.ofPattern("HH:mm", ru)
private val weekdayFormat = DateTimeFormatter.ofPattern("EEE", ru)
private val dayFormat = DateTimeFormatter.ofPattern("d MMM", ru)
private val dayYearFormat = DateTimeFormatter.ofPattern("dd.MM.yy", ru)
private val longDayFormat = DateTimeFormatter.ofPattern("d MMMM", ru)
private val longDayYearFormat = DateTimeFormatter.ofPattern("d MMMM yyyy", ru)

fun clockTime(epoch: Int): String = Instant.ofEpochSecond(epoch.toLong()).atZone(zone).format(clockFormat)

/** Time on the chat list: clock today, weekday this week, then the date. */
fun listTime(epoch: Int, nowEpoch: Long = System.currentTimeMillis() / 1000): String {
    if (epoch == 0) return ""
    val moment = Instant.ofEpochSecond(epoch.toLong()).atZone(zone)
    val now = Instant.ofEpochSecond(nowEpoch).atZone(zone)
    val days = ChronoUnit.DAYS.between(moment.toLocalDate(), now.toLocalDate())
    return when {
        days == 0L -> moment.format(clockFormat)
        days < 7 -> moment.format(weekdayFormat).replaceFirstChar { it.titlecase(ru) }
        moment.year == now.year -> moment.format(dayFormat).trimEnd('.')
        else -> moment.format(dayYearFormat)
    }
}

fun dayHeader(epoch: Int, nowEpoch: Long = System.currentTimeMillis() / 1000): String {
    val moment = Instant.ofEpochSecond(epoch.toLong()).atZone(zone)
    val now = Instant.ofEpochSecond(nowEpoch).atZone(zone)
    return when {
        moment.toLocalDate() == now.toLocalDate() -> "Сегодня"
        moment.toLocalDate() == now.toLocalDate().minusDays(1) -> "Вчера"
        moment.year == now.year -> moment.format(longDayFormat)
        else -> moment.format(longDayYearFormat)
    }
}

fun epochDay(epoch: Int): Long = Instant.ofEpochSecond(epoch.toLong()).atZone(zone).toLocalDate().toEpochDay()

fun formatDuration(seconds: Int): String {
    val minutes = seconds / 60
    return if (minutes >= 60) {
        "%d:%02d:%02d".format(minutes / 60, minutes % 60, seconds % 60)
    } else {
        "%d:%02d".format(minutes, seconds % 60)
    }
}

fun formatSize(bytes: Long): String = when {
    bytes >= 1_073_741_824 -> "%.1f ГБ".format(bytes / 1_073_741_824.0)
    bytes >= 1_048_576 -> "%.1f МБ".format(bytes / 1_048_576.0)
    bytes >= 1024 -> "%.0f КБ".format(bytes / 1024.0)
    else -> "$bytes Б"
}

fun pluralRu(count: Int, one: String, few: String, many: String): String {
    val mod100 = count % 100
    val mod10 = count % 10
    return when {
        mod100 in 11..14 -> many
        mod10 == 1 -> one
        mod10 in 2..4 -> few
        else -> many
    }
}
