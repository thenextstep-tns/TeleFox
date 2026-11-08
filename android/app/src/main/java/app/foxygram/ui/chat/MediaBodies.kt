package app.foxygram.ui.chat

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.CallMade
import androidx.compose.material.icons.automirrored.filled.CallMissed
import androidx.compose.material.icons.automirrored.filled.CallReceived
import androidx.compose.material.icons.filled.ArrowDownward
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.foxygram.model.FeedRow
import app.foxygram.model.ImageRef
import app.foxygram.model.MessageBody
import app.foxygram.model.MessageItem
import app.foxygram.model.StickerFormat
import app.foxygram.model.WebPreview
import app.foxygram.ui.common.Avatar
import app.foxygram.ui.common.LocalFiles
import app.foxygram.ui.common.TelegramImage
import app.foxygram.ui.common.formatDuration
import app.foxygram.ui.common.formatSize
import app.foxygram.ui.common.pluralRu
import app.foxygram.ui.theme.Foxy
import com.airbnb.lottie.compose.LottieAnimation
import com.airbnb.lottie.compose.LottieCompositionSpec
import com.airbnb.lottie.compose.LottieConstants
import com.airbnb.lottie.compose.rememberLottieComposition
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.util.zip.GZIPInputStream

private val MaxMediaHeight = 420.dp
private val MinMediaWidth = 180.dp
private const val ALBUM_GAP_DP = 2

private fun mediaSize(mediaWidth: Int, mediaHeight: Int, maxWidth: Dp): Pair<Dp, Dp> {
    if (mediaWidth <= 0 || mediaHeight <= 0) return maxWidth to maxWidth * 0.75f
    val aspect = mediaWidth.toFloat() / mediaHeight
    var width = maxWidth
    var height = width / aspect
    if (height > MaxMediaHeight) {
        height = MaxMediaHeight
        width = (height * aspect).coerceAtLeast(MinMediaWidth)
    }
    return width to height
}

private fun MessageBody.aspect(): Float = when (this) {
    is MessageBody.Photo -> if (image.height > 0) image.width.toFloat() / image.height else 1f
    is MessageBody.Video -> if (height > 0) width.toFloat() / height else 1f
    else -> 1f
}.coerceIn(0.5f, 2.2f)

@Composable
fun VisualMedia(item: MessageItem, body: MessageBody, width: Dp, actions: MessageActions, overlayMeta: Boolean) {
    Box {
        when (body) {
            is MessageBody.Photo -> {
                val (w, h) = mediaSize(body.image.width, body.image.height, width)
                PhotoTile(body.image, Modifier.size(w, h).clickable { actions.onOpenMedia(item, body) })
            }
            is MessageBody.Video -> {
                val (w, h) = mediaSize(body.width, body.height, width)
                VideoTile(body, Modifier.size(w, h).clickable { actions.onOpenMedia(item, body) })
            }
            is MessageBody.Album -> AlbumGrid(item, body, width, actions)
            else -> Unit
        }
        if (overlayMeta) MetaPill(item, Modifier.align(Alignment.BottomEnd).padding(6.dp))
    }
}

@Composable
private fun PhotoTile(image: ImageRef, modifier: Modifier) {
    TelegramImage(image, modifier, priority = 16)
}

@Composable
private fun VideoTile(body: MessageBody.Video, modifier: Modifier) {
    Box(modifier.background(Color.Black), contentAlignment = Alignment.Center) {
        body.thumb?.let { TelegramImage(it, Modifier.fillMaxSize(), priority = 16) }
        Box(Modifier.size(44.dp).clip(CircleShape).background(Color(0x99000000)), contentAlignment = Alignment.Center) {
            Icon(Icons.Filled.PlayArrow, "Воспроизвести", tint = Color.White, modifier = Modifier.size(28.dp))
        }
        val label = if (body.isGif) "GIF" else formatDuration(body.duration)
        Text(
            label,
            color = Color.White,
            fontSize = 12.sp,
            modifier = Modifier.align(Alignment.TopStart).padding(6.dp)
                .clip(CircleShape).background(Color(0x99000000)).padding(horizontal = 6.dp, vertical = 1.dp),
        )
    }
}

@Composable
private fun AlbumGrid(item: MessageItem, album: MessageBody.Album, width: Dp, actions: MessageActions) {
    val rows = remember(album.items) {
        val items = album.items
        if (items.size % 2 == 1) listOf(items.take(1)) + items.drop(1).chunked(2) else items.chunked(2)
    }
    Column(Modifier.width(width), verticalArrangement = Arrangement.spacedBy(ALBUM_GAP_DP.dp)) {
        rows.forEach { row ->
            val sum = row.sumOf { it.aspect().toDouble() }.toFloat()
            val height = (width / sum).coerceAtMost(280.dp)
            Row(Modifier.fillMaxWidth().height(height), horizontalArrangement = Arrangement.spacedBy(ALBUM_GAP_DP.dp)) {
                row.forEach { member ->
                    val tile = Modifier.weight(member.aspect()).fillMaxHeight().clickable { actions.onOpenMedia(item, member) }
                    when (member) {
                        is MessageBody.Photo -> PhotoTile(member.image, tile)
                        is MessageBody.Video -> VideoTile(member, tile)
                        else -> Box(tile)
                    }
                }
            }
        }
    }
}

@Composable
private fun RoundPlayButton(playing: Boolean, loading: Boolean, background: Color, tint: Color, onClick: () -> Unit) {
    Box(
        Modifier.size(44.dp).clip(CircleShape).background(background).clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        if (loading) {
            CircularProgressIndicator(Modifier.size(24.dp), color = tint, strokeWidth = 2.dp)
        } else {
            Icon(if (playing) Icons.Filled.Pause else Icons.Filled.PlayArrow, null, tint = tint, modifier = Modifier.size(28.dp))
        }
    }
}

@Composable
fun VoiceBody(body: MessageBody.Voice, outgoing: Boolean) {
    val colors = Foxy.colors
    val audio = LocalAudio.current
    val playback by audio.state
    val active = playback.fileId == body.fileId
    val fraction = when {
        active && playback.durationMs > 0 -> playback.positionMs.toFloat() / playback.durationMs
        else -> 0f
    }
    val played = if (outgoing) colors.linkOut else colors.accent
    val rest = (if (outgoing) colors.bubbleOutMeta else colors.textSecondary).copy(alpha = 0.45f)
    Row(Modifier.widthIn(min = 230.dp), verticalAlignment = Alignment.CenterVertically) {
        RoundPlayButton(
            active && playback.playing,
            active && playback.loading,
            played,
            if (outgoing) colors.bubbleOut else colors.onAccent,
        ) { audio.toggle(body.fileId, body.duration) }
        Spacer(Modifier.width(10.dp))
        Column(Modifier.width(180.dp)) {
            Waveform(body.waveform, fraction, played, rest, Modifier.fillMaxWidth().height(26.dp).pointerInput(body.fileId) {
                detectTapGestures { offset -> if (active) audio.seek(offset.x / size.width) }
            })
            Spacer(Modifier.height(2.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                val shown = if (active) (playback.positionMs / 1000).toInt() else body.duration
                Text(formatDuration(shown), color = if (outgoing) colors.bubbleOutMeta else colors.bubbleInMeta, fontSize = 12.sp)
                if (!body.listened && !outgoing) {
                    Spacer(Modifier.width(4.dp))
                    Box(Modifier.size(6.dp).clip(CircleShape).background(colors.accent))
                }
                if (active) {
                    Spacer(Modifier.width(8.dp))
                    Text(
                        "${formatSpeed(playback.speed)}x",
                        color = played,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Medium,
                        modifier = Modifier.clickable { audio.cycleSpeed() },
                    )
                }
            }
        }
    }
}

private fun formatSpeed(speed: Float): String = if (speed % 1f == 0f) speed.toInt().toString() else speed.toString()

@Composable
private fun Waveform(samples: List<Int>, fraction: Float, played: Color, rest: Color, modifier: Modifier) {
    Canvas(modifier) {
        val barWidth = 2.5.dp.toPx()
        val gap = 1.5.dp.toPx()
        val count = ((size.width + gap) / (barWidth + gap)).toInt().coerceAtLeast(1)
        val minHeight = 2.dp.toPx()
        for (index in 0 until count) {
            val sample = if (samples.isEmpty()) 0 else samples[index * samples.size / count]
            val height = (sample / 31f * size.height).coerceAtLeast(minHeight)
            val x = index * (barWidth + gap)
            val color = if (index.toFloat() / count < fraction) played else rest
            drawRoundRect(
                color,
                Offset(x, size.height - height),
                Size(barWidth, height),
                CornerRadius(barWidth / 2),
            )
        }
    }
}

@Composable
fun AudioBody(body: MessageBody.Audio, outgoing: Boolean) {
    val colors = Foxy.colors
    val audio = LocalAudio.current
    val playback by audio.state
    val active = playback.fileId == body.fileId
    val accent = if (outgoing) colors.linkOut else colors.accent
    Row(Modifier.widthIn(min = 220.dp), verticalAlignment = Alignment.CenterVertically) {
        RoundPlayButton(active && playback.playing, active && playback.loading, accent, if (outgoing) colors.bubbleOut else colors.onAccent) {
            audio.toggle(body.fileId, body.duration)
        }
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f, fill = false)) {
            Text(body.title.ifBlank { "Аудио" }, color = colors.text, fontSize = 15.sp, fontWeight = FontWeight.Medium, maxLines = 1, overflow = TextOverflow.Ellipsis)
            val line = listOf(formatDuration(body.duration), body.performer).filter { it.isNotBlank() }.joinToString(" · ")
            Text(line, color = if (outgoing) colors.bubbleOutMeta else colors.bubbleInMeta, fontSize = 13.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
    }
}

@Composable
fun DocumentBody(body: MessageBody.Document, outgoing: Boolean, actions: MessageActions) {
    val colors = Foxy.colors
    val files = LocalFiles.current
    val state by files.observe(body.fileId)
    val accent = if (outgoing) colors.linkOut else colors.accent
    val onAccent = if (outgoing) colors.bubbleOut else colors.onAccent
    Row(
        Modifier.widthIn(min = 220.dp).clickable {
            when {
                state.complete -> actions.onOpenFile(body.fileId, body.name, body.mime)
                state.downloading -> files.cancel(body.fileId)
                else -> files.download(body.fileId, 24)
            }
        },
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(44.dp).clip(CircleShape).background(accent), contentAlignment = Alignment.Center) {
            when {
                state.downloading -> {
                    CircularProgressIndicator({ state.progress }, Modifier.size(32.dp), color = onAccent, strokeWidth = 2.dp)
                    Icon(Icons.Filled.Close, "Отменить", tint = onAccent, modifier = Modifier.size(16.dp))
                }
                state.complete -> Icon(Icons.Filled.Description, null, tint = onAccent, modifier = Modifier.size(24.dp))
                else -> Icon(Icons.Filled.ArrowDownward, "Скачать", tint = onAccent, modifier = Modifier.size(24.dp))
            }
        }
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f, fill = false)) {
            Text(body.name.ifBlank { "Файл" }, color = colors.text, fontSize = 15.sp, fontWeight = FontWeight.Medium, maxLines = 1, overflow = TextOverflow.Ellipsis)
            val size = if (state.downloading) "${formatSize(state.downloaded)} из ${formatSize(body.size)}" else formatSize(body.size)
            Text(size, color = if (outgoing) colors.bubbleOutMeta else colors.bubbleInMeta, fontSize = 13.sp, maxLines = 1)
        }
    }
}

@Composable
fun PollBody(item: MessageItem, body: MessageBody.Poll, actions: MessageActions) {
    val colors = Foxy.colors
    val accent = if (item.outgoing) colors.linkOut else colors.accent
    Column(Modifier.widthIn(min = 240.dp)) {
        Text(body.question, color = colors.text, fontSize = 16.sp, fontWeight = FontWeight.Medium)
        Text(
            (if (body.quiz) "Викторина" else "Опрос") + if (body.closed) " завершён" else "",
            color = if (item.outgoing) colors.bubbleOutMeta else colors.bubbleInMeta,
            fontSize = 13.sp,
        )
        Spacer(Modifier.height(6.dp))
        val showResults = body.voted || body.closed
        body.options.forEachIndexed { index, option ->
            Column(
                Modifier.fillMaxWidth().clickable(enabled = !showResults) { actions.onVote(item, index) }.padding(vertical = 5.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (showResults) {
                        Text("${option.percent}%", color = colors.text, fontSize = 13.sp, fontWeight = FontWeight.Medium, modifier = Modifier.width(38.dp))
                    } else {
                        Box(Modifier.size(20.dp).clip(CircleShape).background(accent.copy(alpha = 0.16f)))
                        Spacer(Modifier.width(10.dp))
                    }
                    Text(option.text, color = colors.text, fontSize = 15.sp, modifier = Modifier.weight(1f))
                    if (option.chosen) Icon(Icons.Filled.Check, null, tint = accent, modifier = Modifier.size(16.dp))
                }
                if (showResults) {
                    Spacer(Modifier.height(3.dp))
                    Box(Modifier.fillMaxWidth().height(3.dp).clip(RoundedCornerShape(2.dp)).background(accent.copy(alpha = 0.16f))) {
                        Box(Modifier.fillMaxWidth(option.percent / 100f).fillMaxHeight().background(accent))
                    }
                }
            }
        }
        Spacer(Modifier.height(2.dp))
        Text(
            "${body.total} " + pluralRu(body.total, "голос", "голоса", "голосов"),
            color = if (item.outgoing) colors.bubbleOutMeta else colors.bubbleInMeta,
            fontSize = 13.sp,
        )
    }
}

@Composable
fun LocationBody(body: MessageBody.Location, actions: MessageActions) {
    val colors = Foxy.colors
    Row(
        Modifier.widthIn(min = 200.dp).clickable { actions.onLink("geo:${body.latitude},${body.longitude}") },
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(44.dp).clip(CircleShape).background(colors.accent), contentAlignment = Alignment.Center) {
            Icon(Icons.Filled.LocationOn, null, tint = colors.onAccent)
        }
        Spacer(Modifier.width(10.dp))
        Column {
            Text(body.title.ifBlank { "Геопозиция" }, color = colors.text, fontSize = 15.sp, fontWeight = FontWeight.Medium)
            Text("%.5f, %.5f".format(body.latitude, body.longitude), color = colors.textSecondary, fontSize = 13.sp)
        }
    }
}

@Composable
fun ContactBody(body: MessageBody.Contact) {
    val colors = Foxy.colors
    Row(Modifier.widthIn(min = 200.dp), verticalAlignment = Alignment.CenterVertically) {
        Avatar(body.name, null, body.userId.toInt(), 44.dp)
        Spacer(Modifier.width(10.dp))
        Column {
            Text(body.name, color = colors.text, fontSize = 15.sp, fontWeight = FontWeight.Medium)
            Text(body.phone, color = colors.textSecondary, fontSize = 13.sp)
        }
    }
}

@Composable
fun CallBody(item: MessageItem, body: MessageBody.Call) {
    val colors = Foxy.colors
    val icon = when {
        body.missed -> Icons.AutoMirrored.Filled.CallMissed
        item.outgoing -> Icons.AutoMirrored.Filled.CallMade
        else -> Icons.AutoMirrored.Filled.CallReceived
    }
    val title = when {
        body.missed -> "Пропущенный звонок"
        item.outgoing -> "Исходящий звонок"
        else -> "Входящий звонок"
    }
    Row(Modifier.widthIn(min = 180.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = if (body.missed) colors.danger else colors.success, modifier = Modifier.size(22.dp))
        Spacer(Modifier.width(10.dp))
        Column {
            Text(title, color = colors.text, fontSize = 15.sp, fontWeight = FontWeight.Medium)
            if (body.duration > 0) Text(formatDuration(body.duration), color = colors.textSecondary, fontSize = 13.sp)
        }
    }
}

@Composable
fun WebCard(web: WebPreview, outgoing: Boolean, actions: MessageActions, modifier: Modifier = Modifier) {
    val colors = Foxy.colors
    val accent = if (outgoing) colors.linkOut else colors.accent
    Row(
        modifier.clip(RoundedCornerShape(5.dp)).background(accent.copy(alpha = 0.12f)).clickable { actions.onLink(web.url) }.height(IntrinsicSize.Min),
    ) {
        Box(Modifier.width(3.dp).fillMaxHeight().background(accent))
        Column(Modifier.padding(horizontal = 8.dp, vertical = 5.dp)) {
            if (web.site.isNotBlank()) Text(web.site, color = accent, fontSize = 14.sp, fontWeight = FontWeight.Medium, maxLines = 1)
            if (web.title.isNotBlank()) Text(web.title, color = colors.text, fontSize = 14.sp, fontWeight = FontWeight.Medium, maxLines = 2, overflow = TextOverflow.Ellipsis)
            if (web.description.isNotBlank()) Text(web.description, color = colors.text, fontSize = 14.sp, maxLines = 4, overflow = TextOverflow.Ellipsis)
            web.photo?.let {
                Spacer(Modifier.height(4.dp))
                TelegramImage(it, Modifier.fillMaxWidth().height(140.dp).clip(RoundedCornerShape(4.dp)), priority = 4)
            }
        }
    }
}

/** Stickers and round videos sit directly on the background, without a bubble. */
@Composable
fun BareMessage(row: FeedRow.Message, maxWidth: Dp, actions: MessageActions) {
    val item = row.item
    when (val body = item.body) {
        is MessageBody.Sticker -> StickerView(row, body)
        is MessageBody.Round -> RoundVideo(item, body, actions)
        else -> Unit
    }
}

@Composable
private fun StickerView(row: FeedRow.Message, body: MessageBody.Sticker) {
    val files = LocalFiles.current
    val state by files.observe(body.fileId)
    LaunchedEffect(body.fileId) { files.download(body.fileId, 12) }
    val side = 180.dp
    val aspect = if (body.height > 0) body.width.toFloat() / body.height else 1f
    Box(Modifier.size(if (aspect >= 1f) side else side * aspect, if (aspect >= 1f) side / aspect else side)) {
        val path = state.localPath
        when {
            body.format == StickerFormat.Lottie && state.complete && path != null -> LottieSticker(path)
            body.format == StickerFormat.Webp && body.fileId != 0 ->
                TelegramImage(ImageRef(body.fileId), Modifier.fillMaxSize(), ContentScale.Fit, priority = 12)
            body.thumb != null -> TelegramImage(body.thumb, Modifier.fillMaxSize(), ContentScale.Fit, priority = 12)
        }
        MetaPill(row.item, Modifier.align(Alignment.BottomEnd))
    }
}

@Composable
private fun LottieSticker(path: String) {
    var json by remember(path) { mutableStateOf<String?>(null) }
    LaunchedEffect(path) {
        json = withContext(Dispatchers.IO) {
            runCatching { GZIPInputStream(File(path).inputStream()).bufferedReader().use { it.readText() } }.getOrNull()
        }
    }
    val source = json ?: return
    val composition by rememberLottieComposition(LottieCompositionSpec.JsonString(source))
    LottieAnimation(composition, iterations = LottieConstants.IterateForever, modifier = Modifier.fillMaxSize())
}

@Composable
private fun RoundVideo(item: MessageItem, body: MessageBody.Round, actions: MessageActions) {
    Box(Modifier.size(220.dp).clip(CircleShape).background(Color.Black).clickable { actions.onOpenMedia(item, body) }, contentAlignment = Alignment.Center) {
        body.thumb?.let { TelegramImage(it, Modifier.fillMaxSize(), priority = 16) }
        Box(Modifier.size(44.dp).clip(CircleShape).background(Color(0x99000000)), contentAlignment = Alignment.Center) {
            Icon(Icons.Filled.PlayArrow, "Воспроизвести", tint = Color.White, modifier = Modifier.size(28.dp))
        }
        Text(
            formatDuration(body.duration),
            color = Color.White,
            fontSize = 12.sp,
            modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 10.dp)
                .clip(CircleShape).background(Color(0x99000000)).padding(horizontal = 6.dp, vertical = 1.dp),
        )
    }
}
