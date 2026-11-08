package app.foxygram.ui.chat

import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.text.InlineTextContent
import androidx.compose.foundation.text.appendInlineContent
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.Placeholder
import androidx.compose.ui.text.PlaceholderVerticalAlign
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.sp
import app.foxygram.model.RichText
import app.foxygram.model.SpanType
import app.foxygram.ui.theme.Foxy

const val LINK_TAG = "link"
private const val META_SPACER = "meta"

fun interface LinkHandler {
    fun open(url: String)
}

fun RichText.toAnnotated(linkColor: Color, codeBackground: Color, metaSpace: Boolean, spoilerColor: Color? = null): AnnotatedString =
    buildAnnotatedString {
        append(text)
        for (span in spans) {
            val end = (span.start + span.length).coerceAtMost(text.length)
            if (span.start !in 0 until end) continue
            when (span.type) {
                SpanType.Bold -> addStyle(SpanStyle(fontWeight = FontWeight.Bold), span.start, end)
                SpanType.Italic -> addStyle(SpanStyle(fontStyle = FontStyle.Italic), span.start, end)
                SpanType.Underline -> addStyle(SpanStyle(textDecoration = TextDecoration.Underline), span.start, end)
                SpanType.Strike -> addStyle(SpanStyle(textDecoration = TextDecoration.LineThrough), span.start, end)
                SpanType.Code, SpanType.Pre ->
                    addStyle(SpanStyle(fontFamily = FontFamily.Monospace, background = codeBackground), span.start, end)
                SpanType.BlockQuote -> addStyle(SpanStyle(fontStyle = FontStyle.Italic), span.start, end)
                SpanType.Spoiler -> if (spoilerColor != null) {
                    addStyle(SpanStyle(color = spoilerColor, background = spoilerColor), span.start, end)
                }
                SpanType.Url -> {
                    addStyle(SpanStyle(color = linkColor), span.start, end)
                    addStringAnnotation(LINK_TAG, text.substring(span.start, end), span.start, end)
                }
                SpanType.TextUrl -> {
                    addStyle(SpanStyle(color = linkColor), span.start, end)
                    addStringAnnotation(LINK_TAG, span.url.orEmpty(), span.start, end)
                }
                SpanType.Mention, SpanType.Hashtag, SpanType.Command -> {
                    addStyle(SpanStyle(color = linkColor), span.start, end)
                    addStringAnnotation(LINK_TAG, text.substring(span.start, end), span.start, end)
                }
                SpanType.Email -> {
                    addStyle(SpanStyle(color = linkColor), span.start, end)
                    addStringAnnotation(LINK_TAG, "mailto:" + text.substring(span.start, end), span.start, end)
                }
                SpanType.Phone -> {
                    addStyle(SpanStyle(color = linkColor), span.start, end)
                    addStringAnnotation(LINK_TAG, "tel:" + text.substring(span.start, end), span.start, end)
                }
            }
        }
        if (metaSpace) appendInlineContent(META_SPACER, " ")
    }

/**
 * Message text. When a time stamp sits in the corner, an invisible placeholder of the same width
 * ends the text, so the stamp shares the last line if it fits and drops below it if not.
 */
@Composable
fun RichTextView(
    text: RichText,
    color: Color,
    linkColor: Color,
    metaWidth: TextUnit,
    onLink: LinkHandler,
    modifier: Modifier = Modifier,
    fontSize: TextUnit = 16.sp,
    lineHeight: TextUnit = 21.sp,
) {
    val colors = Foxy.colors
    var revealed by remember(text) { mutableStateOf(false) }
    val hasSpoiler = remember(text) { text.spans.any { it.type == SpanType.Spoiler } }
    val annotated = remember(text, linkColor, colors.isDark, revealed, metaWidth) {
        text.toAnnotated(
            linkColor,
            colors.surfaceHigh,
            metaSpace = metaWidth.value > 0f,
            spoilerColor = if (hasSpoiler && !revealed) colors.textSecondary else null,
        )
    }
    val inline = remember(metaWidth) {
        if (metaWidth.value > 0f) {
            mapOf(META_SPACER to InlineTextContent(Placeholder(metaWidth, 12.sp, PlaceholderVerticalAlign.TextBottom)) { Box {} })
        } else {
            emptyMap()
        }
    }
    var layout by remember { mutableStateOf<TextLayoutResult?>(null) }
    val hasLinks = remember(annotated) { annotated.getStringAnnotations(LINK_TAG, 0, annotated.length).isNotEmpty() }
    val gestures = if (hasLinks || hasSpoiler) {
        Modifier.pointerInput(annotated) {
            detectTapGestures(onLongPress = null) { position ->
                val result = layout ?: return@detectTapGestures
                val offset = result.getOffsetForPosition(position)
                val link = annotated.getStringAnnotations(LINK_TAG, offset, offset).firstOrNull()
                if (link != null) onLink.open(link.item) else if (hasSpoiler) revealed = true
            }
        }
    } else {
        Modifier
    }
    Text(
        annotated,
        color = color,
        fontSize = fontSize,
        lineHeight = lineHeight,
        inlineContent = inline,
        onTextLayout = { layout = it },
        modifier = modifier.background(Color.Transparent).then(gestures),
    )
}
