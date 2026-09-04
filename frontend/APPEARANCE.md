# Appearance library

Appearance changes presentation, not page meaning, backend authority, or available actions.
The implementation lives in [themes.js](static/assets/themes.js), with shared component styling in
[appearance.css](static/assets/appearance.css). The original application styles remain the layout base.

## Using themes

Settings → Appearance offers Dark, Light, Forest, and Auto. Forest adapts the owner-supplied design
kit's paper, pine, forest-text, green-panel and soft-card treatment. Auto retains the existing
Light/Dark sunrise/system behaviour; it does not switch through custom themes.

Create another theme lets the owner name and save colours, a local font family, colour mode and
card corners. Saving creates an additional choice; it does not replace a built-in. There is no
fixed count limit, but browser storage capacity applies. Themes and selection are local to each
browser/device, not synchronized through Li memory. Clearing browser storage removes custom themes.
Export/import, editing existing themes, and cross-device synchronization are not implemented yet.

When browser storage is blocked, Li still starts with its default appearance and spoken responses
off. Theme selection and voice controls work for the current visit even if preferences cannot be
persisted. Custom-theme creation reports a save failure rather than claiming a theme was saved.

Archivo and Archivo Expanded are preferred for Forest if installed locally, with Segoe UI/system
fallbacks. No remote fonts are loaded. Exact design-kit typography requires a separately reviewed,
licensed local font bundle. Font options currently include modern sans, humanist sans and editorial serif.

## Extending the library

Add a built-in data record to `builtins` in themes.js. Supply a unique ID, name, mode, the seven
colour fields, a supported font key and supported radius. Theme records must not contain scripts,
HTML, external URLs, layout selectors, or arbitrary CSS. Extend font/radius allowlists in code when
a new reviewed family or shape is needed; do not turn the theme creator into a code-execution path.

Validation requires six-digit hex colours and 4.5:1 contrast for main text, secondary text and
accent against the page/card/tile surfaces, plus button text against the accent. These token checks
are not a complete accessibility audit. Recheck real component states and responsive layouts.
Service-worker cache versions must change when theme assets change.

Run `node --test tests-js/*.test.mjs` from frontend, plus the checks in the
[frontend README](README.md#local-validation). Browser verification must cover selection,
custom creation, reload persistence, keyboard focus, and switching away from Auto while its
location callback is still pending. Never use production personal data for visual fixtures.

## Home template analysis

The supplied Home template emphasizes chat and a specialist rail, followed by Today at a glance,
Agenda, Top priorities, and Actions for today. Its meetings, email counts, training plan and
priorities are examples, not owner facts or permission to activate integrations.

Current Home provides chat, specialists, recent conversations, open loops, briefs, artifacts,
and specialist activity. This appearance change preserves those functions and does not implement
new Home data sources.

Recommended next Home arrangement:

1. Greeting and a compact Today at a glance summary, with freshness and unavailable states.
2. The conversation/composer as the primary action, with welcome copy inside its compact header
   rather than a separate presence panel. System agents stay off Home and remain in Specialists
   and Backend/System.
3. Agenda and up to three owner-selected priorities, drawn only from connected real data.
4. A needs-attention section for approvals, overdue commitments, and useful unread briefs.
5. Recent conversations and files below; specialists accessible without occupying most of a phone screen.

Do not infer that every open loop is a top priority, turn missing calendar data into a clear schedule,
invent inbox counts, or automatically execute a suggested action. Home should distinguish a suggestion,
an approved commitment and a completed action. Keep private details behind deliberate interaction when
appropriate. Weather, financial summaries and training cards should be optional and source-labelled,
not permanent empty placeholders.
