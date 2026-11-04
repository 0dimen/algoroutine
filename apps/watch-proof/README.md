# Native watch execution and local persistence proof

KMP commonMain owns step transitions and the versioned persistence journal. SwiftUI and Compose for Wear OS supply native storage adapters. This is a local single-occurrence development slice, not the complete scheduler. The A-style orbit implementation and its current verification boundary are documented below.

## Build

JDK 17, Android SDK 35, Xcode/watchOS simulator runtime. Gradle 8.13, Kotlin 2.2.21, serialization JSON 1.9.0, AGP 8.9.1.

```sh
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
export ANDROID_HOME="$HOME/Library/Android/sdk"
./gradlew --no-daemon --max-workers=1 :shared:jvmTest :shared:linkDebugFrameworkWatchosX64
xcodebuild -project appleWatch/RoutineWatch.xcodeproj -scheme RoutineWatch \
  -sdk watchsimulator -derivedDataPath appleWatch/build -jobs 1 \
  ARCHS=x86_64 ONLY_ACTIVE_ARCH=YES build
# Run after Apple testing and shut down its simulator before starting Wear.
./gradlew --no-daemon --max-workers=1 :wearApp:assembleDebug
```

Apple Silicon: build linkDebugFrameworkWatchosSimulatorArm64 and use ARCHS=arm64. Device target exists but signing/device validation remains pending. Framework paths intentionally use debugFramework. Build the framework before Xcode; this proof is not a release configuration.

## Current behavior

First launch stores a frozen demo definition (ID/version, title, author, step IDs/titles) and empty command journal. 완료 persists the entire candidate journal before publishing the next view. Force-stop/relaunch restores the same current step, terminal state and command receipts. Editing the supplied initial definition does not alter an existing saved occurrence.

Apple writes Application Support/execution-v1.json with Data.atomic. Android uses AtomicFile in internal filesDir and synchronizes the file before completion. Disk work runs off the main thread. Android serializes repository operations across Activity recreation; the shared engine itself requires a single serialized caller.

A read error, corrupt/future-format file or uncertain save displays a retry state. It never silently replaces saved data with a new routine. Retry reloads disk; it does not automatically issue another completion. Identical command replay preserves its historical response and cannot complete another step. UI always displays current view, not a replay's historical view. A late action is protected by expectedRevision and targetStepId.

## Validation boundary

Common unit tests include restart, final-state restore, edited-definition isolation, command replay, failed and ambiguously committed writes, read failure and corruption. See W02 local persistence report for platform execution evidence.

The default v1 proof does not include server integration. The optional v2 profile described below adds local mobile definitions, execution events, parent aggregation, defer/skip/refocus and reservation selection. Authentication, production sync, multi-process writer locking, calendar, speech and Meta remain unimplemented. These remain W02 and later work. Journal format is version 1 and replays at load; it is capped at 10,000 commands and is not a production retention/compaction strategy. Atomic replacement/process-restart tests do not prove physical power-loss durability.

The former -proof-autoplay harness was removed so test launch arguments cannot mutate saved user progress. This demo has no reset button or automatic new occurrence. Do not delete user data to reset it; use a separate disposable test install when needed. Keep simulators/builds sequential and shut down test devices afterward.

## Wear process-restart UI test

Build `:wearApp:assembleDebugAndroidTest`, install the debug app and test APK on a disposable Wear emulator, then run the three phases in order. Each phase is a separate instrumentation run; force-stop the target between runs. The test expects an initially unused persistence file and never resets it.

```sh
adb shell am force-stop app.algoroutine.watchproof
adb shell am instrument -w -e phase before app.algoroutine.watchproof.test/androidx.test.runner.AndroidJUnitRunner
adb shell am force-stop app.algoroutine.watchproof
adb shell am instrument -w -e phase after app.algoroutine.watchproof.test/androidx.test.runner.AndroidJUnitRunner
adb shell am force-stop app.algoroutine.watchproof
adb shell am instrument -w -e phase finished app.algoroutine.watchproof.test/androidx.test.runner.AndroidJUnitRunner
```

## Local mobile/watch integration profile (v2)

Build `:executionServer:installDist`, then run `python3 apps/mobile/run_integrated.py` from the repository root. Mobile is at 127.0.0.1:8780. Create a routine and start it before opening a watch.

Apple simulator launch: `xcrun simctl launch <watch-udid> app.algoroutine.watchproof -demo-server`.
Wear launch: `adb shell am start -n app.algoroutine.watchproof/app.algoroutine.wear.MainActivity --ez demo_server true`.

The flags select the local integration profile; ordinary launch keeps the independent v1 persistence proof. Use a single server process per data directory. The development HTTP transport is not for public deployment. Native integration mode requires the local server and does not claim offline synchronization or production readiness.

Regression: `python3 -m unittest discover -s apps/mobile -p test_execution_integration.py` after building the server. Wear integration UI test uses the explicit class `app.algoroutine.wear.IntegrationUiTest` and expects a newly started fixture with 문서 열기 / 가제 적기 / 키워드 적기. Existing persistence tests must now also specify `-e class app.algoroutine.wear.PersistenceUiTest` to avoid executing both fixtures.

## Native A orbit and gestures (2026-11-01)

Both native shells use a fixed central current planet, a real parent to the left, and ordered peers on its orbit. Vertical swipes / rotary input browse peers; horizontal swipes navigate the actual parent/child relation. The fixed primary action completes (or starts) the displayed execution target. Hold it for 450ms and slide to complete/defer/skip; release without moving or outside the targets cancels. Tap the title for the full text, then Current to return. Apple crown press remains a system action.

The v2 UI uses `RunView.order` so a deferred A in A→B→C appears as B→A→C. The v1 persistence profile uses the same face but supports only completion. The action row is not enabled in v1.

`OrbitUiTest` requires fresh dedicated fixtures (normal three-step or the documented long title); it must not run against real user occurrences. One Wear teardown crash remains a tracked issue despite two subsequent successful repetitions.

## Stability and cross-surface UI flow tests

The Apple project generator now includes `RoutineWatchUITests`; `build-for-testing` and `test-without-building` run against the watchOS simulator. `testCrown` and `testHoldSlide` require a fresh active fixture with 문서 열기 / 가제 적기 / 키워드 적기. Use `scripts/seed_ui_flow.py --active` to create that fixture through the mobile API. Crown is read-only; hold-slide intentionally defers the first step.

For full flow, start `apps/mobile/run_integrated.py --data <new-temporary-directory>`, then run `apps/watch-proof/scripts/seed_ui_flow.py`. It creates two definitions through the mobile API and reserves the first without starting it. Do not run against user data. Apple `testFullFlow` performs Start, complete, other-run focus, return, process relaunch and finish. Wear `FullFlowUiTest#mobileDefinitionStartRefocusAndRestore` leaves step C; force-stop the app and run `FullFlowUiTest#processRestoresAndFinishes` as a separate instrumentation process. Use a fresh server data directory per platform. Before Wear full-flow tests, run `adb reverse tcp:8780 tcp:8780`; test-only mobile API requests use emulator localhost so the existing mobile Host checks remain intact. Remove the reverse mapping afterward. `--use-existing` reuses the single UI-created 통합 검증 루틴 instead of replacing its definition.

Wear `StabilityUiTest#reopenAndRecreateWithoutMutation` needs a freshly active first-step fixture. It repeats ten Activity launches, detail/return, option opening and Activity recreation; each iteration checks unchanged execution revision. A successful bounded repeat does not prove an intermittent framework crash is eliminated.

## Delayed-read regression and startup timing

`run_delayed_read_fixture.py --data <fresh-temp-dir>` runs only local test services (mobile 8780, proxy 8791, engine 8792). Prepare an active fixture, then run `DelayedReadUiTest`: the test holds an old read, completes A, observes B, and releases the old read. B must remain visible. Do not run the normal integrated server at the same time. Test control endpoints exist only in this script.

For startup measurements use the normal server, an active disposable fixture, and `measure_wear_startup.py --samples 3 --output <json-path>`. It force-stops the test app between launches. The remote profile uses ReportDrawnWhen; RoutineStartup logs onCreate→data readiness and RoutineNetwork logs elapsed request time without routine content. Emulator debug samples do not establish real-device SLA/p95 or an improvement over prior unmeasured conditions.

## Native Find → Start → Refocus

The explicit local integration profile now exposes a read-only `/library` proxy to mobile saved definitions. Both native watches show owned/collected cards, author and full steps; Start creates a new occurrence through the existing durable command path. Existing runs and reservations are not rewritten. Together opens existing runs and changes focus only. Library ordering is owned first, then collected; this is not AI ranking or semantic/voice search.

Use fresh `run_integrated.py --data <temporary directory>` per platform, then `scripts/seed_ui_flow.py --with-collected`. Wear: `FullFlowUiTest#findStartAndReturn` (adb reverse 8780); Apple: `RoutineWatchUITests/testFindStartReturn`. Compare reservations before/after and preserve screenshots. Run the existing `OrbitUiTest` only on a fresh server/data directory with **no reservations**, prepared using its **active first-step** fixture (`seed_ui_flow.py --active`). Do not reuse the Find fixture: it leaves a valid reservation and its final-screen expectation is different.

## Situation input and lexical search

Mobile `/api/search` and local watch `/search` accept POST `{ "query": "..." }` (up to 500 characters). Matching candidates are ordered owned → collected → prepared catalog; matches use title/description/steps, not LLM inference. Drafts are excluded; copied catalog entries are deduplicated. A catalog definition can be started by ID/version without silently collecting it. Inputs and results are read-only until an explicit Start.

Wear uses the OS RecognizerIntent result as editable text and falls back to manual text if no provider exists. watchOS TextField provides system input methods, including dictation where available. Neither path auto-searches after dictation. Real microphone transcription/permissions/network quality requires physical-device validation. UI tests using text cannot certify voice.

Watch results now use a bounded stacked-card deck: vertical swipe or crown advances one candidate, with real adjacent cards hinted above/below. Search input is a separate magnifier action; returning from detail preserves the selected card. This is local candidate navigation, not remote pagination.


## A-style polish and recovery audit (2026-11-01)

Shared geometry keeps the current planet centered while real peers rotate into position. Adaptive spacing and safe-area masking may hide distant peers on smaller faces; it never removes them from the model. Connection errors retain the mounted view and draft, block background actions, and restore rotary focus after recovery.

AGP 8.10.1 is used with Kotlin 2.2 and Gradle 8.13/JDK 17. For resource-bounded builds use `--max-workers=1` and `-Dorg.gradle.jvmargs="-Xmx768m -XX:ActiveProcessorCount=2"`.

`assembleBenchmark` creates a separate, non-debuggable, optimized **local test** package `app.algoroutine.watchproof.benchmark` using debug signing and localhost-only cleartext access. It is not a distribution build. `scripts/measure_wear_startup.py --package app.algoroutine.watchproof.benchmark --samples 2 --output <path>` supports comparison against the default debug package. Force-stop the other package before a measurement or UI test; both must not compete for foreground focus. Emulator measurements are cache/environment dependent and do not certify physical startup latency.

The delayed-read test proxy additionally provides `/test/offline` and `/test/online`; these controls are absent from the production engine. `disconnectKeepsSearchDraft` checks draft preservation; `disconnectRestoresRotaryOnSameScreen` checks rotary recovery without recreating the view; `olderPollCannotUndoAcknowledgedCompletion` checks stale-read rejection. Use a fresh active fixture and execute the two read-only recovery tests before completion.

## Frozen current detail, reservation choices, and elapsed windows

Current detail displays the execution snapshot's description, author and all ordered steps. Parent reservation times in child detail are labelled `루틴 시간`; child orbit arcs are not fabricated. Blank legacy descriptions remain blank.

Overlapping reservations use list → preview → explicit Start. Preview and back do not mutate execution; future candidates cannot start. Already-started reservation occurrences are excluded from schedule suggestions and remain reachable through Together.

The local server reconciles running windows every second, on requests, and after restart. At/after the half-open end boundary it writes one internal `expire` command, preserving completed/skipped steps and marking remaining steps/run `elapsed`. It does not start the next reservation or steal another run's focus. `/events` records observation time; the original deadline stays in the definition. An unstarted reservation is not fabricated as a failed run. Expiry write failure blocks publication until storage can be confirmed. Public commands cannot use `expire` or the `system:` ID namespace.

Workspace journals now explicitly write schema 3 and read legacy schema 2 (including its omitted version field). Earlier engines reject schema 3 instead of silently ignoring expiry. The independent v1 local proof journal is unchanged.

New verification: `WindowExpiryTest`, `GapIntegration`, and a fresh `scripts/seed_gap_flow.py` fixture per platform. Wear `GapUiTest#detailChoiceAndExpiry` requires adb reverse 8780; Apple `testDetailChoiceAndExpiry` uses the same fixture. Both deliberately edit the source definition and create a short reservation through normal APIs, then check frozen details and natural return to the next reservation without automatic start. Never run these fixtures on user records.

## Startup scheduling and support-screen recovery (2026-11-02)

In the Wear local integration profile, one `RemoteSession` owns the pending command and initial request. The Activity starts that request before Compose initializes; composition does not send another initial request. The existing epoch guard still rejects stale polling responses. `measure_wear_startup.py --sequential` is a development-only same-binary control that starts the first request after composition instead. Compare interleaved samples on an idle host; do not infer physical-device SLA from emulator samples or conflate data readiness with first-frame time.

Empty, future-reservation and conflicting-reservation screens keep access to already-running occurrences. Entering/leaving the list is read-only; selecting an occurrence changes focus without restarting it. `unavailable` is not an empty schedule: show the retry state and retain Find/Together. Apple support lists reserve the system-clock lane; Wear support lists have full-width actions and restore rotary focus after recovery.

New UI cases: `GapUiTest#idleFutureAndConflictCanRefocus` (fresh `seed_ui_flow.py --active`, adb reverse 8780), then `coldStartReplaysPendingOnce` (same fixture, focuses the original first step). `supportRotaryRecovers` is an isolated composition test. Apple `testColdLaunchReady` is read-only and precedes `testIdleFutureAndConflictCanRefocus` on a fresh active fixture. `unavailableIsNotEmpty` / `testUnavailableIsNotEmpty` require a dedicated fixture with no active focused run and a logically invalid reservation file; never inject that fault into user data. See the linked report for evidence and remaining startup uncertainty.

Startup and support-screen verification (internal report, not included) · Progress flow contract (internal report, not included)

## Physical watch development profile (2026-11-03)

See [device setup](device/README.md) for the expiring authenticated HTTPS bridge, debug-only connection injection, Apple dual-architecture build and Wear installation. Preparation evidence (internal report, not included) separates prepared artifacts from physical-device acceptance, which is still pending. Apple installation requires a valid user signing identity.
