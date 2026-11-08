import java.net.URI
import java.security.MessageDigest
import java.util.zip.ZipFile

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("io.github.takahirom.roborazzi")
}

val repoRoot = rootProject.projectDir.parentFile
val tdlibPin = repoRoot.resolve("tdlib.version").readText().trim()
val tdlibDir = rootProject.projectDir.resolve("tdlib/${tdlibPin.take(12)}")

// Downloads the TDLib our own CI compiled from the pinned commit of Telegram's source.
val fetchTdlib by tasks.registering {
    val marker = tdlibDir.resolve(".complete")
    outputs.file(marker)
    doLast {
        if (marker.exists()) return@doLast
        val tag = "tdlib-${tdlibPin.take(12)}"
        val base = "https://github.com/thenextstep-tns/TeleFox/releases/download/$tag"
        tdlibDir.mkdirs()
        val archive = tdlibDir.resolve("tdlib-android.zip")
        URI("$base/tdlib-android.zip").toURL().openStream().use { input ->
            archive.outputStream().use { input.copyTo(it) }
        }
        val expected = URI("$base/SHA256SUMS").toURL().readText().lineSequence()
            .first { it.endsWith("tdlib-android.zip") }.substringBefore(" ")
        val actual = MessageDigest.getInstance("SHA-256").digest(archive.readBytes())
            .joinToString("") { "%02x".format(it) }
        check(actual == expected) { "tdlib-android.zip checksum mismatch" }
        ZipFile(archive).use { zip ->
            zip.entries().asSequence().filterNot { it.isDirectory }.forEach { entry ->
                val target = tdlibDir.resolve(entry.name)
                target.parentFile.mkdirs()
                zip.getInputStream(entry).use { input -> target.outputStream().use { input.copyTo(it) } }
            }
        }
        archive.delete()
        marker.writeText(tdlibPin)
    }
}

android {
    namespace = "app.foxygram"
    compileSdk = 36

    defaultConfig {
        applicationId = "app.foxygram"
        minSdk = 26
        targetSdk = 35
        versionCode = (project.findProperty("appVersionCode") as String? ?: "1").toInt()
        versionName = project.findProperty("appVersionName") as String? ?: "0.1.0"
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") }
    }

    signingConfigs {
        create("release") {
            storeFile = file(System.getenv("KEYSTORE_PATH") ?: "${System.getProperty("user.home")}/.android/debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    sourceSets["main"].java.srcDir(tdlibDir.resolve("tdlib/java"))
    sourceSets["main"].jniLibs.srcDir(tdlibDir.resolve("tdlib/libs"))

    testOptions {
        unitTests.isIncludeAndroidResources = true
    }

    packaging {
        jniLibs.useLegacyPackaging = false
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
}

tasks.named("preBuild") { dependsOn(fetchTdlib) }

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.04.01")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-process:2.8.7")
    implementation("androidx.core:core-ktx:1.16.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    implementation("io.coil-kt:coil-compose:2.7.0")
    implementation("com.airbnb.android:lottie-compose:6.6.6")
    implementation("androidx.media3:media3-exoplayer:1.6.1")
    implementation("androidx.media3:media3-ui:1.6.1")
    implementation("androidx.camera:camera-camera2:1.4.2")
    implementation("androidx.camera:camera-lifecycle:1.4.2")
    implementation("androidx.camera:camera-view:1.4.2")
    implementation("com.google.zxing:core:3.5.3")

    testImplementation(composeBom)
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.robolectric:robolectric:4.14.1")
    testImplementation("androidx.compose.ui:ui-test-junit4")
    testImplementation("io.github.takahirom.roborazzi:roborazzi:1.43.1")
    testImplementation("io.github.takahirom.roborazzi:roborazzi-compose:1.43.1")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
