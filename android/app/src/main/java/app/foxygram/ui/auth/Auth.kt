package app.foxygram.ui.auth

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import app.foxygram.data.PairingCode
import app.foxygram.td.AuthState
import app.foxygram.td.Telegram
import app.foxygram.ui.theme.Foxy
import com.google.zxing.BarcodeFormat
import com.google.zxing.BinaryBitmap
import com.google.zxing.DecodeHintType
import com.google.zxing.MultiFormatReader
import com.google.zxing.PlanarYUVLuminanceSource
import com.google.zxing.common.HybridBinarizer
import com.google.zxing.qrcode.QRCodeWriter
import kotlinx.coroutines.launch
import java.util.concurrent.Executors

@Composable
private fun AuthLayout(title: String, subtitle: String, content: @Composable () -> Unit) {
    val colors = Foxy.colors
    Column(
        Modifier.fillMaxSize().background(colors.background).windowInsetsPadding(WindowInsets.safeDrawing).imePadding()
            .verticalScroll(rememberScrollState()).padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(title, color = colors.text, fontSize = 22.sp, fontWeight = FontWeight.Medium)
        Spacer(Modifier.height(8.dp))
        Text(subtitle, color = colors.textSecondary, fontSize = 15.sp, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
        Spacer(Modifier.height(24.dp))
        content()
    }
}

@Composable
private fun field(value: String, onValue: (String) -> Unit, label: String, keyboard: KeyboardType, secret: Boolean = false) {
    val colors = Foxy.colors
    OutlinedTextField(
        value, onValue,
        Modifier.fillMaxWidth(),
        label = { Text(label) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = keyboard),
        visualTransformation = if (secret) PasswordVisualTransformation() else VisualTransformation.None,
        colors = OutlinedTextFieldDefaults.colors(
            focusedBorderColor = colors.accent, unfocusedBorderColor = colors.border,
            focusedLabelColor = colors.accent, cursorColor = colors.accent,
            focusedTextColor = colors.text, unfocusedTextColor = colors.text,
        ),
    )
}

@Composable
private fun primary(text: String, enabled: Boolean = true, onClick: () -> Unit) {
    val colors = Foxy.colors
    Button(onClick, Modifier.fillMaxWidth().height(48.dp), enabled = enabled, colors = ButtonDefaults.buttonColors(containerColor = colors.accent, contentColor = colors.onAccent)) {
        Text(text, fontSize = 16.sp)
    }
}

@Composable
fun LoginScreens(telegram: Telegram, state: AuthState) {
    val scope = rememberCoroutineScope()
    var error by remember(state) { mutableStateOf<String?>(null) }
    var busy by remember(state) { mutableStateOf(false) }

    fun submit(action: suspend () -> Unit) {
        busy = true
        error = null
        scope.launch {
            runCatching { action() }.onFailure { error = it.message }
            busy = false
        }
    }

    @Composable
    fun ErrorLine() {
        error?.let { Text(it, color = Foxy.colors.danger, fontSize = 14.sp, modifier = Modifier.padding(top = 12.dp)) }
    }

    when (state) {
        AuthState.WaitPhone -> AuthLayout("Вход в Telegram", "Введите номер телефона с кодом страны.") {
            var phone by remember { mutableStateOf("+") }
            field(phone, { phone = it }, "Номер телефона", KeyboardType.Phone)
            Spacer(Modifier.height(16.dp))
            primary("Продолжить", !busy && phone.length > 5) { submit { telegram.submitPhone(phone) } }
            Spacer(Modifier.height(8.dp))
            TextButton({ submit { telegram.requestQr() } }) { Text("Войти по QR-коду", color = Foxy.colors.accent) }
            ErrorLine()
        }
        is AuthState.WaitQr -> AuthLayout("Вход по QR-коду", "В Telegram на другом устройстве: Настройки, Устройства, Подключить устройство.") {
            val bitmap = remember(state.link) { qrBitmap(state.link) }
            Box(Modifier.clip(RoundedCornerShape(12.dp)).background(Color.White).padding(12.dp)) {
                Image(bitmap.asImageBitmap(), "QR-код", Modifier.size(240.dp))
            }
        }
        is AuthState.WaitCode -> AuthLayout("Код подтверждения", "Код отправлен в Telegram для ${state.phone}.") {
            var code by remember { mutableStateOf("") }
            field(code, { code = it }, "Код", KeyboardType.Number)
            Spacer(Modifier.height(16.dp))
            primary("Войти", !busy && code.isNotBlank()) { submit { telegram.submitCode(code) } }
            ErrorLine()
        }
        is AuthState.WaitPassword -> AuthLayout("Облачный пароль", state.hint.ifBlank { "У вашего аккаунта включён облачный пароль." }) {
            var password by remember { mutableStateOf("") }
            field(password, { password = it }, "Пароль", KeyboardType.Password, secret = true)
            Spacer(Modifier.height(16.dp))
            primary("Войти", !busy && password.isNotBlank()) { submit { telegram.submitPassword(password) } }
            ErrorLine()
        }
        else -> Unit
    }
}

private fun qrBitmap(content: String): Bitmap {
    val size = 720
    val matrix = QRCodeWriter().encode(content, BarcodeFormat.QR_CODE, size, size)
    return Bitmap.createBitmap(size, size, Bitmap.Config.RGB_565).also { bitmap ->
        for (x in 0 until size) for (y in 0 until size) bitmap.setPixel(x, y, if (matrix[x, y]) android.graphics.Color.BLACK else android.graphics.Color.WHITE)
    }
}

@Composable
fun PairScreen(onPaired: (PairingCode) -> Unit) {
    val context = LocalContext.current
    val colors = Foxy.colors
    var scanning by remember { mutableStateOf(false) }
    var pasted by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) scanning = true else error = "Нужен доступ к камере, либо вставьте код вручную."
    }

    AuthLayout("FoxyGram", "Откройте страницу сервера на компьютере и отсканируйте код подключения.") {
        if (scanning) {
            Box(Modifier.size(280.dp).clip(RoundedCornerShape(16.dp)).border(1.dp, colors.border, RoundedCornerShape(16.dp))) {
                QrScanner { value ->
                    val code = PairingCode.parse(value)
                    if (code != null) onPaired(code) else error = "Это не код FoxyGram."
                }
            }
        } else {
            primary("Сканировать код с компьютера") {
                if (context.checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                    scanning = true
                } else {
                    permission.launch(Manifest.permission.CAMERA)
                }
            }
        }
        Spacer(Modifier.height(24.dp))
        field(pasted, { pasted = it }, "Или вставьте код", KeyboardType.Text)
        Spacer(Modifier.height(12.dp))
        OutlinedButton({
            val code = PairingCode.parse(pasted)
            if (code != null) onPaired(code) else error = "Код не распознан."
        }, Modifier.fillMaxWidth().height(48.dp), enabled = pasted.isNotBlank()) { Text("Подключить", color = colors.accent) }
        error?.let { Text(it, color = colors.danger, fontSize = 14.sp, modifier = Modifier.padding(top = 12.dp)) }
    }
}

@Composable
private fun QrScanner(onCode: (String) -> Unit) {
    val context = LocalContext.current
    val lifecycle = LocalLifecycleOwner.current
    val executor = remember { Executors.newSingleThreadExecutor() }
    val reader = remember {
        MultiFormatReader().apply { setHints(mapOf(DecodeHintType.POSSIBLE_FORMATS to listOf(BarcodeFormat.QR_CODE))) }
    }
    var provider by remember { mutableStateOf<ProcessCameraProvider?>(null) }
    DisposableEffect(Unit) {
        onDispose {
            provider?.unbindAll()
            executor.shutdown()
        }
    }
    LaunchedEffect(Unit) {}
    AndroidView(
        factory = { viewContext ->
            val view = PreviewView(viewContext)
            val future = ProcessCameraProvider.getInstance(viewContext)
            future.addListener({
                val camera = future.get()
                provider = camera
                val preview = Preview.Builder().build().also { it.surfaceProvider = view.surfaceProvider }
                val analysis = ImageAnalysis.Builder().setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST).build()
                analysis.setAnalyzer(executor) { image ->
                    val plane = image.planes[0]
                    val bytes = ByteArray(plane.buffer.remaining()).also { plane.buffer.get(it) }
                    val source = PlanarYUVLuminanceSource(bytes, plane.rowStride, image.height, 0, 0, image.width, image.height, false)
                    val result = runCatching { reader.decodeWithState(BinaryBitmap(HybridBinarizer(source))) }.getOrNull()
                    reader.reset()
                    image.close()
                    if (result != null) ContextCompat.getMainExecutor(context).execute { onCode(result.text) }
                }
                camera.unbindAll()
                camera.bindToLifecycle(lifecycle, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis)
            }, ContextCompat.getMainExecutor(viewContext))
            view
        },
        modifier = Modifier.fillMaxSize(),
    )
}
