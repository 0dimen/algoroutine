# Physical-device development connection

This is an expiring **local development** bridge, not a production backend or public deployment. The execution server and mobile app remain on loopback. Watches reach only authenticated, allowlisted execution routes over TLS. A private certificate is trusted only by the debug app; no system-wide certificate installation or disabled hostname verification is used. Meta credentials remain on the Mac.

## Prepare outside Git

From repository root, use the Mac's current private Wi-Fi IPv4 address:

```sh
python3 apps/watch-proof/device/prepare.py --host PRIVATE_IPV4 --output /tmp/algoroutine-device-profile
```

The destination must not already exist or be inside the checkout. It contains a seven-day certificate, private key, random token, `client.json`, and `device.xcconfig`. The directory and files have private permissions. Do not commit, upload, or share this directory, raw build logs, or configured app binaries. Debug apps embed the device token and public certificate. The server private key and Meta key are never embedded.

If the Mac's IP changes, the certificate expires, or `/tmp` is cleared, create a new profile and rebuild both apps. Stop the old gateway to revoke the old token. This version uses one shared device-development token; it is not multi-user access control.

## Build (one heavy build at a time)

From `apps/watch-proof`, set Java 17 and build:

```sh
JAVA_HOME=$(/usr/libexec/java_home -v 17) ./gradlew :shared:linkDebugFrameworkWatchosArm64 :shared:linkDebugFrameworkWatchosDeviceArm64 :wearApp:assembleDebug -PdeviceConfig=/tmp/algoroutine-device-profile/client.json --no-daemon --max-workers=1 '-Dorg.gradle.jvmargs=-Xmx768m -XX:ActiveProcessorCount=2'
```

From `apps/watch-proof/appleWatch`:

```sh
xcodebuild -project RoutineWatch.xcodeproj -scheme RoutineWatch -configuration Debug -destination 'generic/platform=watchOS' -sdk watchos -xcconfig /tmp/algoroutine-device-profile/device.xcconfig -derivedDataPath /tmp/algoroutine-device-build CODE_SIGNING_ALLOWED=NO -jobs 1 build
```

The Apple result is deliberately **unsigned**. Installation requires the user's valid development identity and team. After account setup, rebuild with `CODE_SIGNING_ALLOWED=YES CODE_SIGN_STYLE=Automatic DEVELOPMENT_TEAM=<actual-team-id>` and the actual paired watch destination; do not invent a team or use someone else's account. The project default remains unsigned for existing local proof builds.

Wear produces `wearApp/build/outputs/apk/debug/wearApp-debug.apk`, signed with the local debug key. Install on the connected authorized Wear device with `adb -s <actual-serial> install -r <apk>`. Do not hardcode an emulator serial for physical installation.

No profile: existing simulator `-demo-server` / `demo_server` launch behavior is preserved. Profile: debug apps open the remote current-task flow directly. Release/benchmark builds cannot enable this profile. English/Korean selection is unchanged.

## Run after connection preparation

Run the existing integrated server with a **new isolated data directory** for acceptance testing:

```sh
python3 apps/mobile/run_integrated.py --data /tmp/algoroutine-device-data
```

Create/start a routine through the existing mobile UI at `http://127.0.0.1:8780`. In another terminal, from repository root:

```sh
python3 apps/watch-proof/device/gateway.py --profile /tmp/algoroutine-device-profile --bind PRIVATE_IPV4
```

The default gateway binding is loopback; LAN access requires the explicit profile IP. Port 8792 must be available (the old delayed-read fixture also uses this port and must be stopped). Mac and watch must be on a network with client-to-client communication. Do not forward ports on a router or expose this development gateway to the Internet. Stop the gateway after the test. Mobile browser LAN access is not introduced by this change.

## Acceptance on each physical watch

1. Cold launch shows the same current routine as mobile, in selected English/Korean UI.
2. Complete once: server advances exactly one step; repeat/recovered request cannot advance twice.
3. Find → start another routine → original run remains and can be focused again; reservations unchanged.
4. Disconnect network, observe recoverable read failure, reconnect: current state returns and stale error disappears.
5. Leave unconfirmed mutation pending: no automatic new mutation or duplicate completion.
6. Measure cold display, search response, action acknowledgement on real hardware separately from simulator times.
7. Verify UI gestures, crown/rotary behavior and long-title clipping on the real screen.

Gateway integration tests already cover real KMP search/start/complete and replay semantics. They do not establish physical radio, platform trust behavior, signing, touch usability or latency. Those remain device acceptance checks.

## Tests

```sh
python3 -m unittest discover -s apps/watch-proof/device -p 'test*.py' -v
```

`test_execution_gateway.py` requires the built execution server and mobile dependencies; it uses temporary data and automatically stops owned services.

## Security/target references

- [Apple manual server trust](https://developer.apple.com/documentation/Foundation/performing-manual-server-trust-authentication): custom anchor plus SSL hostname/platform trust evaluation, with exact certificate matching.
- [Android SSL guidance](https://developer.android.com/privacy-and-security/security-ssl): explicit certificate trust store and unchanged hostname verifier; certificate validity checked before each connection.
- [Kotlin Native targets](https://kotlinlang.org/docs/native-target-support.html): `watchosArm64` is arm64_32; `watchosDeviceArm64` is arm64. Framework paths must follow architecture rather than a single watchOS path.
