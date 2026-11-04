plugins { kotlin("jvm"); application }
kotlin { jvmToolchain(17) }
dependencies { implementation(project(":shared")); implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.9.0") }
application { mainClass.set("app.algoroutine.server.MainKt") }
