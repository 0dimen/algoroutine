# How AlgoRoutine uses Meta AI

Users can type a routine name, describe a situation, or say they don't know where to begin. They review a routine and start it themselves before continuing on a watch.

- **Speech to text.** `muse-voice-transcribe-1.0`, called over `wss://api.meta.ai/v1/asr/realtime`. The local server relays push-to-talk PCM audio (24 kHz, mono) and receives cumulative partial transcripts. The user checks or edits the text and presses Find. Speaking alone never starts a recommendation or a routine. Raw audio is not saved.
- **Find an existing routine.** `muse-spark-1.3` (Standard), via `POST https://api.meta.ai/v1/chat/completions` with a strict JSON schema. The model compares the request with the full local candidate list (id, version, source, title, description, steps). It returns up to three existing ids and versions with short reasons, or an explicit `no_fit`. The app copies the content from the original routine, so titles and steps are never rewritten. Author fields, schedules and run history are not sent.
- **Create a new routine.** This happens only after a valid `no_fit`. A separate `muse-spark-1.3` call drafts one short routine with 2–5 concrete steps. The draft is stored as a proposal. It reaches the library only when the user presses Start on the full detail screen.
- **Rest-mode reschedule.** `muse-spark-1.3` proposes a plan for the plans covered by a rest window. The shared Kotlin rules validate that plan. See [REST_RESCHEDULE.md](REST_RESCHEDULE.md).

**Checks and failures**
- The app checks the response structure, candidate identity, versions and duplicates.
- It also checks for stale library state.
- Timeouts and invalid replies stay errors. They never trigger generation or an automatic retry.
- Only one AI request runs at a time.

**Who controls what.** Meta supplies text, choices and drafts. The app's Kotlin Multiplatform execution engine owns starts, step completion, focus and saved state.

**Credentials.** API keys stay on the local server.

**Limits.** Structural checks do not prove that a recommendation is a good fit, or that a generated routine is safe.
