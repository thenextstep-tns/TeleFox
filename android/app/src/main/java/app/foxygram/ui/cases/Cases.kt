package app.foxygram.ui.cases

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.foxygram.model.CaseEvent
import app.foxygram.model.CaseSummary
import app.foxygram.td.Telegram
import app.foxygram.ui.Route
import app.foxygram.ui.common.LabelPill
import app.foxygram.ui.common.listTime
import app.foxygram.ui.theme.Foxy
import kotlinx.coroutines.launch

private val INTENT_LABELS = mapOf(
    "question" to "Вопрос", "request" to "Запрос", "status_update" to "Статус", "payment" to "Оплата",
    "document" to "Документ", "complaint" to "Жалоба", "agreement" to "Договорённость", "smalltalk" to "Разговор",
    "spam" to "Спам", "other" to "Другое",
)

@Composable
fun ScreenBar(title: String, onBack: () -> Unit) {
    val colors = Foxy.colors
    Row(Modifier.fillMaxWidth().background(colors.surface).windowInsetsPadding(WindowInsets.statusBars).height(56.dp), verticalAlignment = Alignment.CenterVertically) {
        IconButton(onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Назад", tint = colors.text) }
        Text(title, color = colors.text, fontSize = 20.sp, fontWeight = FontWeight.Medium, modifier = Modifier.padding(start = 8.dp), maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

@Composable
fun EmptyNote(text: String) {
    Box(Modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
        Text(text, color = Foxy.colors.textSecondary, fontSize = 15.sp, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
    }
}

@Composable
fun CasesScreen(telegram: Telegram, onBack: () -> Unit, navigate: (Route) -> Unit) {
    val colors = Foxy.colors
    var cases by remember { mutableStateOf<List<CaseSummary>?>(null) }
    var failed by remember { mutableStateOf(false) }
    var closed by remember { mutableStateOf(false) }

    LaunchedEffect(closed) {
        val api = telegram.serverApi
        if (!api.configured) {
            failed = true
            return@LaunchedEffect
        }
        runCatching { api.cases(if (closed) "closed" else "open") }
            .onSuccess {
                cases = it
                failed = false
            }
            .onFailure { failed = true }
    }

    Column(Modifier.fillMaxSize().background(colors.background)) {
        ScreenBar("Дела", onBack)
        Row(Modifier.fillMaxWidth().background(colors.surface).padding(horizontal = 8.dp)) {
            TextButton({ closed = false }) { Text("Открытые", color = if (!closed) colors.accent else colors.textSecondary) }
            TextButton({ closed = true }) { Text("Закрытые", color = if (closed) colors.accent else colors.textSecondary) }
        }
        val list = cases
        when {
            failed -> EmptyNote("Компьютер с сервером сейчас недоступен. Дела появятся, когда он снова будет в сети.")
            list == null -> Unit
            list.isEmpty() -> EmptyNote("Пока нет дел. Выберите чаты для Claude, и здесь появятся темы, которые в них обсуждают.")
            else -> LazyColumn(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.navigationBars)) {
                items(list, key = { it.id }) { case -> CaseRow(case) { navigate(Route.CaseDetail(case.id)) } }
            }
        }
    }
}

@Composable
private fun CaseRow(case: CaseSummary, onClick: () -> Unit) {
    val colors = Foxy.colors
    Column(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 16.dp, vertical = 12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(case.title, color = colors.text, fontSize = 16.sp, fontWeight = FontWeight.Medium, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
            Spacer(Modifier.width(8.dp))
            Text(listTime(case.updatedAt.toInt()), color = colors.textSecondary, fontSize = 13.sp)
        }
        if (case.summary.isNotBlank()) {
            Spacer(Modifier.height(3.dp))
            Text(case.summary, color = colors.textSecondary, fontSize = 14.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
        Spacer(Modifier.height(5.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
            if (case.needsReview > 0) LabelPill("Проверить", colors.warning)
            Text(case.chats.joinToString(", "), color = colors.accent, fontSize = 13.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
    }
    HorizontalDivider(color = colors.border, thickness = 0.5.dp)
}

@Composable
fun CaseDetailScreen(telegram: Telegram, caseId: Long, onBack: () -> Unit, navigate: (Route) -> Unit) {
    val colors = Foxy.colors
    val scope = rememberCoroutineScope()
    var data by remember { mutableStateOf<Pair<CaseSummary, List<CaseEvent>>?>(null) }
    var failed by remember { mutableStateOf(false) }
    var reload by remember { mutableIntStateOf(0) }

    LaunchedEffect(caseId, reload) {
        runCatching { telegram.serverApi.caseEvents(caseId) }.onSuccess { data = it }.onFailure { failed = true }
    }

    fun change(block: suspend () -> Unit) {
        scope.launch {
            runCatching { block() }
            reload++
        }
    }

    Column(Modifier.fillMaxSize().background(colors.background)) {
        ScreenBar(data?.first?.title ?: "Дело", onBack)
        val current = data
        if (failed) {
            EmptyNote("Компьютер с сервером сейчас недоступен.")
        } else if (current != null) {
            val (case, events) = current
            LazyColumn(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.navigationBars).padding(horizontal = 12.dp)) {
                item {
                    Column(Modifier.padding(vertical = 12.dp)) {
                        if (case.summary.isNotBlank()) Text(case.summary, color = colors.text, fontSize = 15.sp)
                        if (case.entities.isNotEmpty()) {
                            Spacer(Modifier.height(8.dp))
                            Text(case.entities.joinToString("  ·  "), color = colors.textSecondary, fontSize = 13.sp)
                        }
                        Row {
                            TextButton({ change { telegram.serverApi.setCaseStatus(caseId, if (case.status == "open") "closed" else "open") } }) {
                                Text(if (case.status == "open") "Закрыть дело" else "Открыть снова", color = colors.accent)
                            }
                        }
                    }
                }
                items(events, key = { it.burstId }) { event ->
                    EventCard(
                        event,
                        onOpen = { navigate(Route.Chat(event.chatId)) },
                        onConfirm = { change { telegram.serverApi.confirmLink(event.burstId) } },
                        onRemove = { change { telegram.serverApi.unlink(event.burstId) } },
                    )
                }
            }
        }
    }
}

@Composable
private fun EventCard(event: CaseEvent, onOpen: () -> Unit, onConfirm: () -> Unit, onRemove: () -> Unit) {
    val colors = Foxy.colors
    Column(
        Modifier.fillMaxWidth().padding(bottom = 10.dp).clip(RoundedCornerShape(12.dp)).background(colors.surface).clickable(onClick = onOpen).padding(12.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(event.chatTitle, color = colors.accent, fontSize = 14.sp, fontWeight = FontWeight.Medium, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
            INTENT_LABELS[event.intent]?.let { LabelPill(it, colors.textSecondary) }
            if (event.urgency == "high") LabelPill("Срочно", colors.danger)
        }
        if (event.summary.isNotBlank()) {
            Spacer(Modifier.height(4.dp))
            Text(event.summary, color = colors.text, fontSize = 15.sp)
        }
        event.messages.takeLast(3).forEach { message ->
            Spacer(Modifier.height(4.dp))
            Text(
                (if (message.outgoing) "Вы" else message.sender) + ": " + message.text,
                color = colors.textSecondary, fontSize = 13.sp, maxLines = 2, overflow = TextOverflow.Ellipsis,
            )
        }
        if (event.needsReview) {
            Row {
                TextButton(onConfirm) { Text("Верно", color = colors.accent) }
                TextButton(onRemove) { Text("Не относится", color = colors.danger) }
            }
        }
    }
}
