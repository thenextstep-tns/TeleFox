package app.foxygram.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.remember
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

@Immutable
data class FoxyColors(
    val isDark: Boolean,
    val background: Color,
    val surface: Color,
    val surfaceHigh: Color,
    val border: Color,
    val text: Color,
    val textSecondary: Color,
    val accent: Color,
    val accentStrong: Color,
    val onAccent: Color,
    val accentSoft: Color,
    val bubbleIn: Color,
    val bubbleInMeta: Color,
    val bubbleOut: Color,
    val bubbleOutMeta: Color,
    val link: Color,
    val linkOut: Color,
    val success: Color,
    val warning: Color,
    val danger: Color,
    val mutedBadge: Color,
    val servicePill: Color,
    val onServicePill: Color,
    val avatar: List<Color>,
    val name: List<Color>,
)

/** GitHub's near-black with its purple accent. */
val DarkColors = FoxyColors(
    isDark = true,
    background = Color(0xFF0D1117),
    surface = Color(0xFF161B22),
    surfaceHigh = Color(0xFF21262D),
    border = Color(0xFF30363D),
    text = Color(0xFFE6EDF3),
    textSecondary = Color(0xFF8B949E),
    accent = Color(0xFFA371F7),
    accentStrong = Color(0xFF8957E5),
    onAccent = Color(0xFFFFFFFF),
    accentSoft = Color(0x29A371F7),
    bubbleIn = Color(0xFF161B22),
    bubbleInMeta = Color(0xFF8B949E),
    bubbleOut = Color(0xFF36275E),
    bubbleOutMeta = Color(0xFFB4A5D4),
    link = Color(0xFFBC8CFF),
    linkOut = Color(0xFFD2B8FF),
    success = Color(0xFF3FB950),
    warning = Color(0xFFD29922),
    danger = Color(0xFFF85149),
    mutedBadge = Color(0xFF484F58),
    servicePill = Color(0xCC21262D),
    onServicePill = Color(0xFFE6EDF3),
    avatar = listOf(
        Color(0xFF8957E5), Color(0xFF1F6FEB), Color(0xFF238636), Color(0xFF9E6A03),
        Color(0xFFDA3633), Color(0xFFBF3989), Color(0xFF0E7C86), Color(0xFF6E7681),
    ),
    name = listOf(
        Color(0xFFFF7B72), Color(0xFFFFA657), Color(0xFFD2A8FF), Color(0xFF3FB950),
        Color(0xFF39C5CF), Color(0xFF79C0FF), Color(0xFFF778BA),
    ),
)

val LightColors = FoxyColors(
    isDark = false,
    background = Color(0xFFFFFFFF),
    surface = Color(0xFFF6F8FA),
    surfaceHigh = Color(0xFFEAEEF2),
    border = Color(0xFFD0D7DE),
    text = Color(0xFF1F2328),
    textSecondary = Color(0xFF59636E),
    accent = Color(0xFF8250DF),
    accentStrong = Color(0xFF6E40C9),
    onAccent = Color(0xFFFFFFFF),
    accentSoft = Color(0x1F8250DF),
    bubbleIn = Color(0xFFF6F8FA),
    bubbleInMeta = Color(0xFF59636E),
    bubbleOut = Color(0xFFEBE1FC),
    bubbleOutMeta = Color(0xFF6E5A96),
    link = Color(0xFF6639BA),
    linkOut = Color(0xFF5128A0),
    success = Color(0xFF1A7F37),
    warning = Color(0xFF9A6700),
    danger = Color(0xFFCF222E),
    mutedBadge = Color(0xFF8C959F),
    servicePill = Color(0xB3EAEEF2),
    onServicePill = Color(0xFF1F2328),
    avatar = listOf(
        Color(0xFF8250DF), Color(0xFF0969DA), Color(0xFF1A7F37), Color(0xFF9A6700),
        Color(0xFFCF222E), Color(0xFFBF3989), Color(0xFF0E7C86), Color(0xFF6E7781),
    ),
    name = listOf(
        Color(0xFFCF222E), Color(0xFFBC4C00), Color(0xFF8250DF), Color(0xFF1A7F37),
        Color(0xFF0E7C86), Color(0xFF0969DA), Color(0xFFBF3989),
    ),
)

val LocalFoxyColors = staticCompositionLocalOf { DarkColors }

object Foxy {
    val colors: FoxyColors
        @Composable @ReadOnlyComposable get() = LocalFoxyColors.current
}

enum class ThemeMode { System, Dark, Light }

private val FoxyTypography = Typography(
    titleLarge = TextStyle(fontSize = 20.sp, fontWeight = FontWeight.Medium, lineHeight = 24.sp),
    titleMedium = TextStyle(fontSize = 16.sp, fontWeight = FontWeight.Medium, lineHeight = 20.sp),
    bodyLarge = TextStyle(fontSize = 16.sp, lineHeight = 21.sp),
    bodyMedium = TextStyle(fontSize = 15.sp, lineHeight = 20.sp),
    bodySmall = TextStyle(fontSize = 13.sp, lineHeight = 16.sp),
    labelSmall = TextStyle(fontSize = 12.sp, lineHeight = 14.sp),
)

@Composable
fun FoxyTheme(mode: ThemeMode = ThemeMode.Dark, content: @Composable () -> Unit) {
    val dark = when (mode) {
        ThemeMode.System -> isSystemInDarkTheme()
        ThemeMode.Dark -> true
        ThemeMode.Light -> false
    }
    val colors = if (dark) DarkColors else LightColors
    val scheme = remember(dark) {
        if (dark) {
            darkColorScheme(
                primary = colors.accent, onPrimary = colors.onAccent, secondary = colors.accent,
                background = colors.background, onBackground = colors.text,
                surface = colors.surface, onSurface = colors.text,
                surfaceVariant = colors.surfaceHigh, onSurfaceVariant = colors.textSecondary,
                surfaceContainer = colors.surface, surfaceContainerHigh = colors.surfaceHigh,
                surfaceContainerLow = colors.surface, surfaceContainerHighest = colors.surfaceHigh,
                outline = colors.border, outlineVariant = colors.border, error = colors.danger,
            )
        } else {
            lightColorScheme(
                primary = colors.accent, onPrimary = colors.onAccent, secondary = colors.accent,
                background = colors.background, onBackground = colors.text,
                surface = colors.background, onSurface = colors.text,
                surfaceVariant = colors.surfaceHigh, onSurfaceVariant = colors.textSecondary,
                surfaceContainer = colors.surface, surfaceContainerHigh = colors.surfaceHigh,
                surfaceContainerLow = colors.surface, surfaceContainerHighest = colors.surfaceHigh,
                outline = colors.border, outlineVariant = colors.border, error = colors.danger,
            )
        }
    }
    CompositionLocalProvider(LocalFoxyColors provides colors) {
        MaterialTheme(colorScheme = scheme, typography = FoxyTypography, content = content)
    }
}
