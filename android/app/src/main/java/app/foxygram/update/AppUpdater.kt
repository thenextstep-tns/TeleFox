package app.foxygram.update

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Environment
import android.provider.Settings
import android.widget.Toast
import androidx.core.content.FileProvider
import app.foxygram.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

data class Release(val version: String, val notes: String, val apkUrl: String)

/** Finds and installs FoxyGram builds published from the foxygram branch. */
object AppUpdater {
    private const val RELEASES = "https://api.github.com/repos/thenextstep-tns/TeleFox/releases?per_page=30"
    private const val TAG_PREFIX = "foxygram-v"

    suspend fun latest(): Release? = withContext(Dispatchers.IO) {
        runCatching {
            val connection = URL(RELEASES).openConnection() as HttpURLConnection
            connection.connectTimeout = 10_000
            connection.readTimeout = 15_000
            connection.setRequestProperty("Accept", "application/vnd.github+json")
            val rows = JSONArray(connection.inputStream.bufferedReader().use { it.readText() })
            (0 until rows.length()).map(rows::getJSONObject)
                .filter { it.getString("tag_name").startsWith(TAG_PREFIX) }
                .mapNotNull { row ->
                    val assets = row.getJSONArray("assets")
                    val apk = (0 until assets.length()).map(assets::getJSONObject).firstOrNull { it.getString("name").endsWith(".apk") }
                        ?: return@mapNotNull null
                    Release(row.getString("tag_name").removePrefix(TAG_PREFIX), row.optString("body"), apk.getString("browser_download_url"))
                }
                .maxWithOrNull { a, b -> compare(a.version, b.version) }
                ?.takeIf { compare(it.version, BuildConfig.VERSION_NAME) > 0 }
        }.getOrNull()
    }

    private fun compare(a: String, b: String): Int {
        val left = a.split('.').map { it.toIntOrNull() ?: 0 }
        val right = b.split('.').map { it.toIntOrNull() ?: 0 }
        for (index in 0 until maxOf(left.size, right.size)) {
            val difference = left.getOrElse(index) { 0 } - right.getOrElse(index) { 0 }
            if (difference != 0) return difference
        }
        return 0
    }

    suspend fun install(context: Context, release: Release, onProgress: (Int) -> Unit) {
        if (!context.packageManager.canRequestPackageInstalls()) {
            Toast.makeText(context, "Разрешите установку и нажмите «Обновить» ещё раз", Toast.LENGTH_LONG).show()
            context.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${context.packageName}")))
            return
        }
        val file = withContext(Dispatchers.IO) { download(context, release, onProgress) }
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", file)
        context.startActivity(
            Intent(Intent.ACTION_VIEW)
                .setDataAndType(uri, "application/vnd.android.package-archive")
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK),
        )
    }

    private fun download(context: Context, release: Release, onProgress: (Int) -> Unit): File {
        val directory = context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS)!!
        directory.listFiles()?.forEach { it.delete() }
        val target = File(directory, "FoxyGram-${release.version}.apk")
        val connection = URL(release.apkUrl).openConnection() as HttpURLConnection
        val total = connection.contentLengthLong
        var done = 0L
        connection.inputStream.use { input ->
            target.outputStream().use { output ->
                val buffer = ByteArray(64 * 1024)
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    output.write(buffer, 0, count)
                    done += count
                    if (total > 0) onProgress((done * 100 / total).toInt())
                }
            }
        }
        return target
    }
}
