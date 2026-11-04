# Mobile app (local web)

Local single-user web app served on `127.0.0.1:8780`. It covers the routine library (SQLite), Find (keyword search, plus Meta recommend and generate with `--meta`), voice relay (`--meta`), the rest-mode proposal, and the bridge to the Kotlin execution server on `127.0.0.1:8791`.

- Run: see the root [README](../../README.md). `run_integrated.py` starts both servers.
- Data: the default directory is `~/.emotion-scheduler/integration`. `rest_demo.py prepare` creates a separate disposable fixture. `--demo-clock` works only on such a fixture.
- Meta key: `MODEL_API_KEY`, or a file at `~/.config/algoroutine/meta-api-key`. Calls happen only with `--meta`.
- Security: loopback bind only. Host, Origin and request headers are checked. Raw requests are not logged.
- Tests: `python3 -m unittest test_rest_reschedule test_store test_server ...`. They use no paid calls.
- Browser checks: the `test_*_browser.py` and `verify_*_browser.py` scripts need Chrome with CDP on 9333 (see `cdp.py`).
- Known issue: `test_browser`, `test_language_browser`, `test_meta_browser` and `test_voice_browser` still expect an older start screen. They fail and need updating.
- Paid test: `test_voice_browser.py --live-voice` makes a real, billed Meta call.
