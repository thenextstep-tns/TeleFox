package app.foxygram.ui.brain

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.foxygram.data.BrainAction
import app.foxygram.data.BrainMark
import app.foxygram.data.BrainPanel
import app.foxygram.data.BrainRun
import app.foxygram.ui.common.LabelPill
import app.foxygram.ui.theme.Foxy
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

/** The mark of every message Brain analysed in the open chat, by TDLib message id. Empty outside Brain's chats. */
val LocalBrainMarks = compositionLocalOf<Map<Long, BrainMark>> { emptyMap() }

private val STATUS = mapOf(
    "open" to "Ждёт вашего решения",
    "approved" to "Одобрено, выполняется",
    "executed" to "Одобрено и выполнено",
    "failed" to "Одобрено, но не получилось",
    "rejected" to "Отклонено: ничего не отправлено",
    "answered" to "Отвечено",
    "dismissed" to "Скрыто: ничего не отправлено",
)

private val ru = Locale.forLanguageTag("ru")
private val brainClock = DateTimeFormatter.ofPattern("HH:mm", ru)
private val brainDay = DateTimeFormatter.ofPattern("d MMM, HH:mm", ru)

/** Brain writes times as "YYYY-MM-DD HH:MM:SS" in this PC's local time. */
fun brainTime(at: String): String {
    val moment = runCatching { LocalDateTime.parse(at.trim().replace(' ', 'T')) }.getOrNull() ?: return ""
    return if (moment.toLocalDate() == LocalDate.now()) moment.format(brainClock) else moment.format(brainDay)
}

/** A small round mark next to a message Brain analysed. */
@Composable
fun BrainMarkBadge(mark: BrainMark, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val colors = Foxy.colors
    val tint = when (mark) {
        BrainMark.Waiting -> colors.warning
        BrainMark.Failed -> colors.danger
        else -> colors.accent
    }
    Box(
        modifier.padding(horizontal = 4.dp).size(24.dp).clip(CircleShape).background(tint.copy(alpha = 0.16f)).clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        if (mark == BrainMark.Working) {
            CircularProgressIndicator(Modifier.size(12.dp), color = tint, strokeWidth = 2.dp)
        } else {
            Icon(Icons.Filled.SmartToy, "Brain", tint = tint, modifier = Modifier.size(14.dp))
        }
    }
}

/** What was tapped, for the top of the sheet. */
data class BrainMessagePreview(val who: String, val time: String, val text: String)

/**
 * Brain's view of the open chat: for one message when [selectedIds] is set, otherwise its recent runs.
 * [onDecide] gets the action, the decision ("approve", "reject", "answer", "dismiss"), and an optional text and reason.
 */
@Composable
fun BrainPanelContent(
    panel: BrainPanel?,
    error: String?,
    selectedIds: List<Long>?,
    preview: BrainMessagePreview?,
    onShowAll: () -> Unit,
    onJump: (BrainRun) -> Unit,
    onDecide: (BrainAction, String, String?, String?) -> Unit,
    modifier: Modifier = Modifier,
) {
    val colors = Foxy.colors
    Column(modifier.fillMaxWidth().padding(horizontal = 16.dp)) {
        val jobs = panel?.jobs?.joinToString(", ") { it.name }.orEmpty()
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Filled.SmartToy, null, tint = colors.accent, modifier = Modifier.size(22.dp))
            Spacer(Modifier.width(10.dp))
            Text(if (jobs.isEmpty()) "Brain" else "Brain · $jobs", color = colors.text, fontSize = 17.sp, fontWeight = FontWeight.Medium,
                maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        Spacer(Modifier.height(10.dp))
        if (error != null) Banner(error)
        panel?.pausedJobs?.forEach { Banner("Работа «${it.name}» на паузе: новые сообщения не анализируются.") }
        if (panel == null) {
            if (error == null) Hint("Загрузка…")
            return@Column
        }
        if (selectedIds != null) {
            Label("Сообщение")
            if (preview != null) {
                Row(Modifier.fillMaxWidth().padding(bottom = 10.dp).clip(RoundedCornerShape(6.dp)).background(colors.accentSoft).height(IntrinsicSize.Min)) {
                    Box(Modifier.width(3.dp).fillMaxHeight().background(colors.accent))
                    Column(Modifier.padding(horizontal = 10.dp, vertical = 6.dp)) {
                        Text("${preview.who} · ${preview.time}", color = colors.accent, fontSize = 14.sp, fontWeight = FontWeight.Medium)
                        Text(preview.text, color = colors.text, fontSize = 14.sp, maxLines = 4, overflow = TextOverflow.Ellipsis)
                    }
                }
            }
            val runs = panel.runsFor(selectedIds)
            if (runs.isEmpty()) {
                Hint("Brain не разбирал это сообщение." + if (panel.pausedJobs.isNotEmpty()) " Пока работа на паузе, новые сообщения не разбираются." else "")
            }
            runs.forEach { RunCard(it, null, onDecide) }
            TextButton(onShowAll, Modifier.padding(start = 0.dp)) { Text("Все разборы в этом чате", color = colors.accent) }
        } else {
            Hint("Нажмите на сообщение, чтобы увидеть, что решил Brain и что он предлагает сделать.")
            if (panel.items.isEmpty()) {
                Hint("В этом чате Brain пока ничего не разбирал.")
            } else {
                Label("Последние разборы")
                panel.items.take(20).forEach { RunCard(it, onJump, onDecide) }
            }
        }
        Spacer(Modifier.height(16.dp))
    }
}

@Composable
private fun Banner(text: String) {
    val colors = Foxy.colors
    Text(
        text, color = colors.warning, fontSize = 14.sp,
        modifier = Modifier.fillMaxWidth().padding(bottom = 10.dp).clip(RoundedCornerShape(10.dp))
            .background(colors.warning.copy(alpha = 0.12f)).padding(horizontal = 12.dp, vertical = 10.dp),
    )
}

@Composable
private fun Hint(text: String) {
    Text(text, color = Foxy.colors.textSecondary, fontSize = 14.sp, modifier = Modifier.padding(bottom = 10.dp))
}

@Composable
private fun Label(text: String) {
    Text(text, color = Foxy.colors.textSecondary, fontSize = 13.sp, fontWeight = FontWeight.Medium, modifier = Modifier.padding(top = 4.dp, bottom = 8.dp))
}

@Composable
private fun SectionLabel(text: String) {
    Text(text.uppercase(), color = Foxy.colors.textSecondary, fontSize = 12.sp, fontWeight = FontWeight.Medium,
        letterSpacing = 0.4.sp, modifier = Modifier.padding(top = 10.dp))
}

@Composable
private fun RunCard(run: BrainRun, onJump: ((BrainRun) -> Unit)?, onDecide: (BrainAction, String, String?, String?) -> Unit) {
    val colors = Foxy.colors
    Column(Modifier.fillMaxWidth().padding(bottom = 10.dp).clip(RoundedCornerShape(12.dp)).background(colors.background).padding(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            LabelPill(run.jobName, colors.accent)
            Text("разбор №${run.runId} · ${brainTime(run.at)}", color = colors.textSecondary, fontSize = 13.sp, maxLines = 1)
            when {
                run.working -> Row(verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(Modifier.size(12.dp), color = colors.accent, strokeWidth = 2.dp)
                    Spacer(Modifier.width(5.dp))
                    Text("Работает…", color = colors.accent, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                }
                run.status == "error" -> LabelPill("Ошибка", colors.danger)
            }
        }
        if (onJump != null && run.messageIds.isNotEmpty()) {
            val count = run.messageIds.size
            Text(
                if (count > 1) "К сообщениям ($count)" else "К сообщению", color = colors.accent, fontSize = 14.sp, fontWeight = FontWeight.Medium,
                modifier = Modifier.padding(top = 6.dp).clickable { onJump(run) },
            )
        }
        if (run.decisions.isNotEmpty()) {
            SectionLabel("Решение")
            run.decisions.forEach { Text(it, color = colors.text, fontSize = 15.sp, modifier = Modifier.padding(top = 4.dp)) }
        } else if (run.working) {
            Text("Brain разбирает сообщения…", color = colors.textSecondary, fontSize = 15.sp, modifier = Modifier.padding(top = 6.dp))
        }
        if (run.actions.isNotEmpty()) {
            SectionLabel("Предлагает")
            run.actions.forEach { ActionCard(it, onDecide) }
        } else if (!run.working && run.decisions.isNotEmpty()) {
            Text("Ничего не предлагает.", color = colors.textSecondary, fontSize = 13.sp, modifier = Modifier.padding(top = 8.dp))
        }
        if (run.summary.isNotBlank() && !run.working) {
            Text(run.summary, color = colors.textSecondary, fontSize = 13.sp, maxLines = 5, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 8.dp))
        }
    }
}

@Composable
private fun ActionCard(action: BrainAction, onDecide: (BrainAction, String, String?, String?) -> Unit) {
    val colors = Foxy.colors
    val statusColor = when (action.status) {
        "open" -> colors.warning
        "failed" -> colors.danger
        "executed", "answered" -> colors.success
        "approved" -> colors.accent
        else -> colors.textSecondary
    }
    Column(Modifier.fillMaxWidth().padding(top = 8.dp).border(1.dp, colors.border, RoundedCornerShape(10.dp)).padding(10.dp)) {
        Text(if (action.isQuestion) "Вопрос к вам" else "Действие: ${action.actionType.ifBlank { "—" }}", color = colors.textSecondary, fontSize = 13.sp)
        action.to?.let { Text("Кому: $it", color = colors.text, fontSize = 13.sp, fontWeight = FontWeight.Medium, modifier = Modifier.padding(top = 2.dp)) }
        if (action.isQuestion) action.question?.let { Text(it, color = colors.text, fontSize = 15.sp, modifier = Modifier.padding(top = 4.dp)) }
        action.text?.let {
            Text(it, color = colors.text, fontSize = 15.sp, modifier = Modifier.fillMaxWidth().padding(top = 6.dp).clip(RoundedCornerShape(8.dp))
                .background(colors.bubbleOut).padding(horizontal = 10.dp, vertical = 8.dp))
        }
        if (action.isQuestion && action.options.isNotEmpty() && !action.isOpen) {
            Text("Варианты: " + action.options.joinToString(" · "), color = colors.textSecondary, fontSize = 13.sp, modifier = Modifier.padding(top = 4.dp))
        }
        Text(STATUS[action.status] ?: action.status, color = statusColor, fontSize = 13.sp, fontWeight = FontWeight.Medium, modifier = Modifier.padding(top = 6.dp))
        action.answer?.let { Text("Ваш ответ: $it", color = colors.text, fontSize = 13.sp, modifier = Modifier.padding(top = 4.dp)) }
        action.reason?.let { Text("Пояснение: $it", color = colors.textSecondary, fontSize = 13.sp, modifier = Modifier.padding(top = 4.dp)) }
        action.result?.let { Text(it, color = colors.textSecondary, fontSize = 13.sp, modifier = Modifier.padding(top = 4.dp)) }
        if (action.isOpen) Controls(action, onDecide)
    }
}

/** Your answer goes to Brain, which applies its own rules: nothing is sent to anyone without "approve". */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun Controls(action: BrainAction, onDecide: (BrainAction, String, String?, String?) -> Unit) {
    val colors = Foxy.colors
    var mode by remember(action.id) { mutableStateOf<String?>(null) }
    var draft by remember(action.id) { mutableStateOf(action.text.orEmpty()) }
    var confirm by remember(action.id) { mutableStateOf<String?>(null) }

    if (action.isQuestion) {
        FlowRow(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            action.options.forEach { option ->
                Text(
                    option, color = colors.accent, fontSize = 14.sp,
                    modifier = Modifier.clip(RoundedCornerShape(16.dp)).border(1.dp, colors.accent, RoundedCornerShape(16.dp))
                        .clickable { onDecide(action, "answer", option, null) }.padding(horizontal = 12.dp, vertical = 6.dp),
                )
            }
        }
        var answer by remember(action.id) { mutableStateOf("") }
        OutlinedTextField(answer, { answer = it }, Modifier.fillMaxWidth().padding(top = 6.dp), placeholder = { Text("Свой ответ") }, minLines = 2)
        Row {
            TextButton({ if (answer.isNotBlank()) onDecide(action, "answer", answer.trim(), null) }) { Text("Ответить", color = colors.accent) }
            TextButton({ onDecide(action, "dismiss", null, null) }) { Text("Скрыть", color = colors.textSecondary) }
        }
        return
    }

    FlowRow(Modifier.padding(top = 2.dp)) {
        TextButton({ confirm = action.text.orEmpty() }) { Text("Одобрить", color = colors.accent) }
        TextButton({ mode = "edit" }) { Text("Изменить", color = colors.accent) }
        TextButton({ mode = "reject" }) { Text("Отклонить", color = colors.danger) }
        TextButton({ onDecide(action, "dismiss", null, null) }) { Text("Скрыть", color = colors.textSecondary) }
    }
    when (mode) {
        "edit" -> {
            OutlinedTextField(draft, { draft = it }, Modifier.fillMaxWidth(), label = { Text("Текст") }, minLines = 2)
            TextButton({ if (draft.isNotBlank()) confirm = draft.trim() }) { Text("Одобрить с изменениями", color = colors.accent) }
        }
        "reject" -> {
            var reason by remember(action.id) { mutableStateOf("") }
            OutlinedTextField(reason, { reason = it }, Modifier.fillMaxWidth(), placeholder = { Text("Почему (необязательно)") }, minLines = 2)
            TextButton({ onDecide(action, "reject", null, reason.trim().ifBlank { null }) }) { Text("Отклонить", color = colors.danger) }
        }
    }
    confirm?.let { text ->
        AlertDialog(
            onDismissRequest = { confirm = null },
            title = { Text("Одобрить?") },
            text = { Text((action.to?.let { "Кому: $it\n\n" } ?: "") + text.ifBlank { action.actionType }) },
            confirmButton = {
                TextButton({
                    confirm = null
                    onDecide(action, "approve", text.takeIf { mode == "edit" }, null)
                }) { Text("Одобрить", color = colors.accent) }
            },
            dismissButton = { TextButton({ confirm = null }) { Text("Отмена") } },
            containerColor = colors.surface,
        )
    }
}
