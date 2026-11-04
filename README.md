# AlgoRoutine

**Stop safely. Come back to where you were.**

AlgoRoutine is a routine-and-schedule app for moments when your day suddenly falls apart. You say what is happening and it finds a small routine to run. If you need rest, it rearranges the rest of your day in one step. A watch walks you through one step at a time, and your place is kept so you can pick up again later.

## What it does

1. **Say it → Meta recommends.** Type or speak a sentence like "I suddenly started crying. I can't focus anymore." Meta AI reads it and picks the routine that fits.
2. **Your routines first.** It picks from routines you made or saved. If none fits, it drafts a new short routine. You see every step before you press Start.
3. **Rest without losing the day.** Starting a rest routine opens one batch proposal for the plans it pushes aside: move, not this time, keep, or decide later. Meta proposes and the app's rules check every item: no overlaps, nothing past the end of the day or a deadline, and required plans stay put. Suggestions that fail a rule are marked *Needs check* and get a rule-based alternative. Change only what you want, then apply everything with one button.
4. **One step at a time on the watch.** Native watchOS (SwiftUI) and Wear OS (Compose) apps show only the current step.
5. **Keep your place.** Interrupted runs stay where you left them. Moved plans keep their original time in their history.

## Meta models

| Use | Model |
| --- | --- |
| Speech to text (push-to-talk) | `muse-voice-transcribe-1.0` (realtime WebSocket) |
| Recommend an existing routine / draft a new one | `muse-spark-1.3` (Chat Completions, strict JSON schema) |
| Rest-mode batch reschedule proposal | `muse-spark-1.3` (strict JSON schema; one call, no automatic retry) |

The model only proposes. Saving, starting, and schedule changes are validated by the app. A timeout or a bad reply falls back to a rule-based plan that is labelled as such. More detail: [docs/META_AI.md](docs/META_AI.md) and [docs/REST_RESCHEDULE.md](docs/REST_RESCHEDULE.md).

## How it fits together

```
 Phone browser (apps/mobile/web)
        │  127.0.0.1:8780
        ▼
 Python local server (apps/mobile) ──────▶ Meta AI API (only with --meta)
   library (SQLite), find, recommend,
   voice relay, rest proposal
        │  127.0.0.1:8791
        ▼
 Kotlin execution server (apps/watch-proof/executionServer)
   uses the shared KMP core (apps/watch-proof/shared):
   runs, steps, reservations, rest validation
        ▲
        │
 watchOS app (appleWatch)  ·  Wear OS app (wearApp)
```

## Run it yourself in 3 steps

You need Python 3.10+ and JDK 17. No API key is needed.

```sh
# 1. Build the Kotlin execution server
(cd apps/watch-proof && ./gradlew --no-daemon :executionServer:installDist)

# 2. Make a fresh demo fixture (sample routines and an afternoon schedule, starting at 14:00)
python3 apps/mobile/rest_demo.py prepare --data /tmp/algoroutine-demo --now 14:00

# 3. Run it, then open http://127.0.0.1:8780
python3 apps/mobile/run_integrated.py --data /tmp/algoroutine-demo --demo-clock --demo-reset
```

Outside macOS, set `JAVA_HOME` to a JDK 17 first. Step 2 refuses a directory that already exists, so use a new path each time.

Try it like this:
1. Open **Find** and type "I suddenly started crying. I can't focus anymore."
2. Start **Burnout reset** to see the rest proposal, change one item, and press **Apply all at once**.
3. Run `python3 apps/mobile/rest_demo.py advance --minutes 180` to jump ahead three hours and see the moved plans.

Without a key, Find uses local keyword search and the rest proposal is rule-based.

**Optional: with Meta AI.** Set `MODEL_API_KEY` and add `--meta` to step 3. For voice input, install the voice dependency first: `python3 -m venv .venv && .venv/bin/pip install -r apps/mobile/requirements.txt`. Then run step 3 with `.venv/bin/python`. Calls with `--meta` are real, billed API calls.

### Tests

```sh
(cd apps/watch-proof && ./gradlew --no-daemon :shared:jvmTest)
(cd apps/mobile && python3 -m unittest test_rest_reschedule test_store test_server test_search test_recommendation test_meta_integration test_execution_integration test_voice test_localization)
```

The browser checks (`apps/mobile/verify_rest_browser.py` and others) need a headless Chrome with `--remote-debugging-port=9333`. They use a mock Meta reply.

The watch apps build with Xcode (watchOS simulator) and Android SDK 35 (Wear OS emulator). See [apps/watch-proof/README.md](apps/watch-proof/README.md).

## Demo video

_Link coming soon._

## Limits

- The mobile app is a local web app on `127.0.0.1`. It is not a published phone app, and there are no accounts or cloud sync.
- The watch apps are checked on the watchOS simulator and the Wear OS emulator only. They have not been tested on a real watch.
- Meta replies are checked for structure and against the app's rules. This does not prove that a recommendation is always a good fit.
- "Not this time" is shown only inside the app. It never cancels anything in an external calendar.

## License

MIT © 2026 ChaeWon Kim
