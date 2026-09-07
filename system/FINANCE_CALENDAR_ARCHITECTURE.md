# Finance and Calendar workspace architecture

**Status:** Accepted repository design; Calendar read UI and private portfolio foundation are
implemented in source. Portfolio schema 0.42 is not applied and these changes are not deployed merely
because this document or code is merged.

## Context

The owner wants two first-class Li workspaces:

- **My Finances**, with separate Avanza and Crypto views, owner-entered positions, current value, and
  individual and aggregate unrealized gain or loss.
- **Calendar**, with a detailed Monday-to-Sunday week and a compact month directly below it.

Financial records are highly sensitive under the
[Security & Privacy Policy](security-policy.md). Calendar reads and writes already have a governed
Li-owned adapter and approval boundary described in the [repository README](../README.md#google-calendar-provider-setup).
No equivalent portfolio store or approved brokerage/market-data provider existed when this decision
was made.

## Decision

### Navigation and responsive layout

Desktop navigation exposes My Finances and Calendar directly. Mobile navigation keeps five stable
targets—Home, Calendar, Finances, Specialists, and More—so touch targets remain usable. More links to
Briefs, History & Artifacts, Backend / System, and Settings without removing those destinations.

Calendar opens with a Monday-to-Sunday week. Desktop and tablet widths use columns; narrow phone
screens use a day-by-day agenda to preserve readable event titles and 44-pixel controls. Saturday and
Sunday use a subtle, theme-derived red tint rather than a fixed bright warning colour. The six-week
month grid appears below the week, with event counts rather than private titles. Selecting a date
moves the week focus. Times are labelled with the device display timezone.

Finances uses Avanza and Crypto as account categories inside one workspace. Summary cards show
current value, cost basis, and unrealized gain/loss. Holdings become compact cards on narrow screens.

### Calendar boundary

The browser calls a signed-in BFF endpoint with a bounded date range. The BFF constructs a
`calendar.search` request and cannot forward a browser-selected Calendar mutation. The private
backend continues to own the OAuth credential and provider. Reads require no action approval; event
creation remains available only through Li's existing approval-enforcing executor.

The UI fetches on opening, week navigation, Today, or explicit Refresh. It does not poll in the
background. A request covers at most the 42-day month grid and returns at most 100 events. All-day
Google events retain date-only, exclusive-end semantics so timezone conversion cannot move them to a
different day. Event descriptions are not shown in the overview; month cells show counts only.

### Portfolio boundary

“Avanza” is an owner-defined account view, not a direct Avanza integration. Li must never ask for,
store, or automate entry of an Avanza password, bank credential, wallet private key, seed phrase, or
recovery phrase. No unofficial brokerage API, browser scraping, or trade execution is permitted by
this design.

Schema 0.42 adds one owner-scoped table behind `SECURITY DEFINER` functions. Row-level security is
enabled and forced. The normal Li database capability can list, create/update, and archive holdings
through those functions; it has no direct table access. Theo, owner-confirmation, retention, client,
and service roles receive no portfolio function or table authority. Archiving hides a position but
retains its audit record.

Each holding stores quantity, average unit cost, cost currency, and an optional owner-entered current
price with a server timestamp. Calculations are deterministic. Totals are grouped by currency and
never sum unlike currencies. A holding with no price, or a quote currency different from its cost
currency, is explicitly unpriced. Values are unrealized estimates, not tax or performance records.

Portfolio records are not automatically added to Li chat, specialist packets, canonical memory, or
proactive briefs. A later feature that shares a bounded portfolio summary with James requires a
separate privacy and relevance review.

## Market-data provider position

Automatic quotes are intentionally not activated in the foundation:

- No official Avanza developer integration was selected. Unofficial private APIs and credential
  automation are outside the boundary.
- Free market-data products commonly impose small quotas, delayed data, attribution requirements, or
  paid real-time licensing. A configured key alone does not prove no-additional-charge coverage.
- Crypto identifiers, stock exchange suffixes, quote currencies, corporate actions, and FX conversion
  require an explicit normalized instrument model before prices can be trusted.

A later quote adapter must identify source, price time, delay/freshness class, currency, and failure
state; cache boundedly; avoid background polling; and never enable overages. Provider activation and
any metered operation require current no-additional-charge evidence and the external-action approval
required by [AGENTS.md](../AGENTS.md).

## Security and privacy consequences

- Browser sessions and the server-side BFF remain the only web entry; no database or provider
  credentials enter JavaScript.
- Financial holdings stay in private runtime data, not Git or browser storage.
- Calendar failure is shown as unavailable, never as an empty confirmed calendar.
- Portfolio capability failure is shown as unavailable, never as an empty confirmed portfolio.
- No portfolio mutation represents a market transaction. UI copy and API names must preserve that
  distinction.
- Tests use synthetic positions and events only. Personal holdings and Calendar data are not read for
  implementation evidence.

## Migration, deployment, and rollback

Migration 042 is immutable, forward-only history. Applying it requires the exact staging migration
authorization, a fresh validated encrypted pre-0.42 backup, full isolated restore, rehearsal, and
authority-denial validation described in the [Migration workflow](../docs/MIGRATION_WORKFLOW.md).

Deploy the matching backend and web as coordinated reviewed candidates only after schema 0.42 is
available. Application rollback can return traffic to the immediately preceding privacy-safe
revision, but does not remove schema 0.42 or portfolio records. Database rollback means restore and
recovery, not down-migration. No automatic quote provider is part of that deployment.

## Acceptance

Repository acceptance requires:

1. Full migration-manifest replay through schema 0.42, including Li/backend allow and all direct,
   Theo, owner-confirmation, retention, anonymous, authenticated, and service-role denials.
2. Backend validation for owner scoping, decimals, quote completeness, currency-separated totals,
   archive confirmation, and unavailable-schema failure.
3. BFF validation proving Calendar is read-only and bounded and portfolio payloads contain no
   credential fields.
4. Browser tests for Monday-first dates, all-day exclusive ranges, same-currency calculations,
   five-item mobile navigation, accessible controls, phone/tablet layout, empty states, and errors.
5. Separately authorized staged migration/deployment evidence, followed by owner checks on Android
   phone, Android tablet, and installed Windows PWA before claiming device acceptance.

Automatic quote accuracy, realized gain/loss, tax calculations, broker synchronization, and trading
remain explicitly outside this foundation.
