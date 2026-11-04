# Language contract

English is the default on a new installation, independent of OS language. Korean is the other enabled language. Mobile selects language in the header; watches expose a large language-switch button in Find → Enter a request. With two enabled languages it cycles between English and 한국어. Selection is device-local and persisted; cross-device language synchronization is not implemented.

`en.json` and `ko.json` are the source of application copy. Korean phrases are stable message IDs, not the runtime default. Do not rename a key just to revise wording. Named placeholders must match. Routine titles, descriptions, author names, user input, and existing run snapshots are data and are never translated or overwritten by language selection. Existing Korean demo/library content therefore remains Korean in English UI.

`registry.json` defines names and speech settings. Run `python3 scripts/generate_localizations.py` after editing; commit the generated browser, Kotlin and Swift catalogs. Python validation errors read the same source. Unknown language falls back to English. Browser counts use Intl.PluralRules; add appropriate plural keys when introducing languages with more categories.

Meta recommendation reasons and new generated routines request the selected language at creation. Existing user routines remain verbatim. Browser voice uses the selected language bias; Wear's OS recognizer uses its language tag. This is an instruction/bias, not a guarantee of monolingual output. Watch search currently searches the local library/catalog; paid Meta recommendation/generation remains the mobile flow.

## Adding a language

1. Translate the complete catalog with context (action, error, accessibility label, small-watch constraint), not isolated words. Preserve placeholders.
2. Add registry metadata, regenerate, and run `PYTHONPATH=apps/mobile apps/mobile/.venv/bin/python -m unittest test_localization`.
3. Test English fallback, persistence, unsaved text preservation, source content integrity, numbers/time and accessibility. Check rectangular and round watch clipping with long strings and larger fonts.
4. Have a fluent reviewer assess clarity, tone, action reversibility, and naturalness. Automated key/placeholder checks do not prove translation quality. Record reviewer/language/version before release. English/Korean currently have agent-reviewed copy; no professional/native-speaker certification is claimed.
5. RTL, language-specific plural systems beyond the current English/Korean patterns, and full OS-format integration need explicit implementation and layout review before enabling such languages. Registry extensibility alone does not provide these.

Keep UI language and content language separate. Do not send existing user content to a translation service merely because the UI language changes.
