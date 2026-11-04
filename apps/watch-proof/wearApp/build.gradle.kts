import groovy.json.JsonSlurper

plugins {
    id("com.android.application")
    kotlin("android")
    id("org.jetbrains.kotlin.plugin.compose")
}
val deviceProfile = providers.gradleProperty("deviceConfig").orNull?.let {
    @Suppress("UNCHECKED_CAST")
    JsonSlurper().parse(file(it)) as Map<String, Any>
}
fun quoted(value: Any?): String = "\"" + (value?.toString() ?: "").replace("\\", "\\\\").replace("\"", "\\\"") + "\""
android {
    namespace = "app.algoroutine.wear"
    compileSdk = 35
    defaultConfig { applicationId = "app.algoroutine.watchproof"; minSdk = 30; targetSdk = 35; versionCode = 1; versionName = "0.1"; testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner" }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
    // Local-only performance build. Never signed or configured for distribution.
    defaultConfig {
        for (key in listOf("host", "port", "token", "certificate")) buildConfigField("String", "DEVICE_" + key.uppercase(), "\"\"")
    }
    buildTypes {
        getByName("debug") {
            deviceProfile?.let { profile ->
                for (key in listOf("host", "port", "token", "certificate")) buildConfigField("String", "DEVICE_" + key.uppercase(), quoted(profile[key]))
            }
        }
        create("benchmark") {
            initWith(getByName("release"))
            applicationIdSuffix = ".benchmark"
            signingConfig = signingConfigs.getByName("debug")
            isDebuggable = false
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "benchmark-rules.pro")
            matchingFallbacks += listOf("release")
        }
    }
    buildFeatures { compose = true; buildConfig = true }
}
dependencies {
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4:1.7.8")
    implementation(project(":shared"))
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.9.0")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.wear.compose:compose-material:1.4.1")
    implementation("androidx.compose.ui:ui-tooling-preview:1.7.8")
}
