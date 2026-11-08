package app.foxygram.ui.chat

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.waitForUpOrCancellation
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Reply
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.foxygram.ui.common.formatDuration
import app.foxygram.ui.theme.Foxy

data class ComposerTarget(val isEdit: Boolean, val title: String, val text: String)

@Composable
fun Composer(
    value: TextFieldValue,
    onValue: (TextFieldValue) -> Unit,
    target: ComposerTarget?,
    recordingSeconds: Int?,
    onCancelTarget: () -> Unit,
    onSend: () -> Unit,
    onAttach: () -> Unit,
    onRecordStart: () -> Unit,
    onRecordStop: (cancel: Boolean) -> Unit,
    modifier: Modifier = Modifier,
) {
    val colors = Foxy.colors
    Column(modifier.fillMaxWidth().background(colors.surface)) {
        if (target != null) TargetBar(target, onCancelTarget)
        Row(Modifier.fillMaxWidth().heightIn(min = 52.dp), verticalAlignment = Alignment.Bottom) {
            if (recordingSeconds != null) {
                Row(Modifier.weight(1f).height(52.dp).padding(start = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(10.dp).clip(CircleShape).background(colors.danger))
                    Spacer(Modifier.width(8.dp))
                    Text(formatDuration(recordingSeconds), color = colors.text, fontSize = 16.sp)
                    Spacer(Modifier.width(16.dp))
                    Text("Отпустите, чтобы отправить", color = colors.textSecondary, fontSize = 14.sp, maxLines = 1)
                }
            } else {
                IconButton(onAttach, Modifier.size(52.dp)) { Icon(Icons.Filled.AttachFile, "Прикрепить", tint = colors.textSecondary) }
                Box(Modifier.weight(1f).heightIn(min = 52.dp).padding(vertical = 14.dp), contentAlignment = Alignment.CenterStart) {
                    if (value.text.isEmpty()) Text("Сообщение", color = colors.textSecondary, fontSize = 17.sp)
                    BasicTextField(
                        value,
                        onValue,
                        textStyle = TextStyle(color = colors.text, fontSize = 17.sp, lineHeight = 22.sp),
                        cursorBrush = SolidColor(colors.accent),
                        maxLines = 7,
                        keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }
            when {
                target?.isEdit == true -> SendButton(Icons.Filled.Check, "Сохранить", onSend)
                value.text.isNotBlank() -> SendButton(Icons.AutoMirrored.Filled.Send, "Отправить", onSend)
                else -> MicButton(onRecordStart, onRecordStop)
            }
        }
    }
}

@Composable
private fun SendButton(icon: androidx.compose.ui.graphics.vector.ImageVector, label: String, onClick: () -> Unit) {
    Box(Modifier.size(52.dp).clickable(onClick = onClick), contentAlignment = Alignment.Center) {
        Icon(icon, label, tint = Foxy.colors.accent)
    }
}

@Composable
private fun MicButton(onStart: () -> Unit, onStop: (Boolean) -> Unit) {
    Box(
        Modifier.size(52.dp).pointerInput(Unit) {
            awaitEachGesture {
                val down = awaitFirstDown()
                down.consume()
                onStart()
                val up = waitForUpOrCancellation()
                onStop(up == null)
            }
        },
        contentAlignment = Alignment.Center,
    ) {
        Icon(Icons.Filled.Mic, "Голосовое сообщение", tint = Foxy.colors.textSecondary)
    }
}

@Composable
private fun TargetBar(target: ComposerTarget, onCancel: () -> Unit) {
    val colors = Foxy.colors
    Row(Modifier.fillMaxWidth().height(48.dp), verticalAlignment = Alignment.CenterVertically) {
        Spacer(Modifier.width(14.dp))
        Icon(if (target.isEdit) Icons.Filled.Edit else Icons.AutoMirrored.Filled.Reply, null, tint = colors.accent, modifier = Modifier.size(22.dp))
        Spacer(Modifier.width(12.dp))
        Box(Modifier.width(2.dp).fillMaxHeight().padding(vertical = 8.dp).background(colors.accent))
        Spacer(Modifier.width(8.dp))
        Column(Modifier.weight(1f)) {
            Text(target.title, color = colors.accent, fontSize = 14.sp, fontWeight = FontWeight.Medium, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(target.text, color = colors.text, fontSize = 14.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        IconButton(onCancel) { Icon(Icons.Filled.Close, "Отменить", tint = colors.textSecondary) }
    }
}
