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
Custom themes can be edited, and appearance files can be transferred manually between devices.
Automatic cross-device synchronization is not implemented.

### Edit and transfer

- Select a custom theme, then **Edit selected theme**. Save validates the changes and updates that
  theme in place. A failed save leaves the previous theme intact. **Cancel editing** discards the draft.
- **Create from current look** copies the displayed palette into a new draft. Built-in themes remain
  read-only. After saving, the editor edits that new theme; use Create again for another separate theme.
- **Export current look** downloads `li-appearance.json`. With Auto selected, it exports the currently
  displayed Light/Dark palette, not a location or automatic-switching rule. Browser download handling varies.
- **Import appearance** reads a local JSON file (16 KB maximum) into the editor without uploading it,
  changing the active appearance, or saving it. Review and press Save to add a new theme. Imported names
  may match existing names, but new identifiers prevent replacement. No existing themes are removed.

The version-1 transfer envelope contains `format: "li-appearance"`, `version: 1`, and a `theme` with only
the validated name, mode, colours, font key and corner radius. IDs, CSS, URLs, scripts and unknown fields
are not accepted. Unsupported versions and unreadable palettes are rejected before saving. No conversation,
profile photo, credential or location is included. Theme names are included: avoid personal information in
names if you plan to share a file. These portable files are not backups of Li's private data.

The controls reuse existing theme tokens, semantic buttons/labels and 44px targets. Status messages are
announced, Edit is disabled for built-ins/Auto, and opening a draft focuses its name. Slow imports are
ignored when a newer import or editor action supersedes them. Keyboard, small-screen and real-browser
download/import checks remain part of release acceptance, beyond token-contrast and automated tests.

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
and specialist activity. A compact **Today at a glance** panel summarizes counts from those four
existing live sections: recent conversations, open commitments, unread briefs and saved files.
Each section fails independently; an unavailable source displays an em dash and the freshness line
states how many sections loaded instead of turning missing data into zero. The panel introduces no
new Home data source and never infers agenda or priority status from those counts.

The conversation/composer remains the primary action, with welcome copy inside its compact header
rather than a separate presence panel. System agents stay off Home and remain in Specialists and
Backend/System. Recent conversations and files stay below the main workspace. On phone-sized views,
Home shows the first three active-first specialist cards and a **View all specialists** control; the
full roster remains present on larger screens and on the Specialists page.

Recommended remaining Home work:

1. Agenda and up to three owner-selected priorities, drawn only from connected real data.
2. A consolidated needs-attention section for approvals, overdue commitments, and useful unread briefs.
3. Deployed and physical-device validation of information density and responsive behavior.

Do not infer that every open loop is a top priority, turn missing calendar data into a clear schedule,
invent inbox counts, or automatically execute a suggested action. Home should distinguish a suggestion,
an approved commitment and a completed action. Keep private details behind deliberate interaction when
appropriate. Weather, financial summaries and training cards should be optional and source-labelled,
not permanent empty placeholders.
