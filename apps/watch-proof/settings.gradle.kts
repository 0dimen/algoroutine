pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }
dependencyResolutionManagement { repositories { google(); mavenCentral() } }
rootProject.name = "RoutineWatchProof"
include(":shared", ":wearApp")

include(":executionServer")
