plugins { kotlin("multiplatform"); kotlin("plugin.serialization") }
kotlin {
    jvm { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) } }
    watchosX64()
    watchosSimulatorArm64()
    watchosArm64()
    watchosDeviceArm64()
    targets.withType<org.jetbrains.kotlin.gradle.plugin.mpp.KotlinNativeTarget>().configureEach {
        binaries.framework { baseName = "RoutineCore"; isStatic = true }
    }
    sourceSets { commonMain.dependencies { implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.9.0") }; commonTest.dependencies { implementation(kotlin("test")) } }
}
