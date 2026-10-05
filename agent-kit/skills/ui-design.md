# Skill — UI/UX Design & Implementation

## Role

Act as a senior UI/UX designer and frontend implementation specialist.

## Design principles

Prioritize:

- hierarchy
- clarity
- consistency
- spacing
- readability
- interaction feedback
- responsive behavior

## When a reference is provided

Analyze:

- layout
- typography
- colors
- spacing
- component patterns
- navigation
- visual hierarchy
- responsive behavior

Reproduce the intended design language without blindly copying implementation details.

## Design system

Reuse existing:

- buttons
- inputs
- cards
- dialogs
- tables
- badges
- alerts
- navigation

Do not create duplicate visual patterns.

## Required UI states

Where relevant, provide:

- loading
- empty
- error
- disabled
- hover
- focus
- active
- success

## Forms

Provide:

- clear labels
- validation feedback
- submission state
- useful error messages
- keyboard-friendly interaction

## Responsive quality

Do not simply shrink desktop layouts.

Reconsider:

- information density
- navigation
- table presentation
- action placement
- spacing
- typography

## Visual review

Before delivery inspect the affected screens for:

- alignment
- spacing
- overflow
- inconsistent styling
- broken responsive behavior
- missing states
- weak visual hierarchy

## TSS dashboard design language

- **Purpose:** a dense, glanceable monitoring screen for a single operator on a desktop/laptop. Mobile is secondary but must work.
- **Theme:** dark default with a light theme. Define colours as CSS tokens in `globals.css`; components use tokens only.
- **Semantic colours:**
  - `--up` and `--down` for directional values
  - `--warn` (stale / warming-up)
  - `--crit` (failed / halted)
  - `--muted`
  - All must meet AA contrast on both themes.
- Direction always uses **icon + sign + colour** (▲ +1.82 % / ▼ −2.10 %), never colour alone.
- **Typography:** Inter for UI, JetBrains Mono (`tabular-nums`) for all numbers, prices and timestamps. Bundle both with `next/font`.
- **Density:**
  - table rows 36–40 px
  - 12–13 px numeric text
  - panel padding on a 4/8 px scale
  - sticky table headers
  - horizontal scroll inside the panel (never on the page)
- **State badges:**
  - LONG_BUILDUP (up)
  - SHORT_BUILDUP (down)
  - SHORT_COVERING (up, outlined)
  - LONG_UNWINDING (down, outlined)
  - NEUTRAL (muted)
  - UNRELIABLE (warn, hatched)
- **Flags:** small chips with abbreviations (FUND✓, CRWD-L, CRWD-S, SQZ, SPOT✓, TF≠, WARM). Each has a tooltip with the full meaning.
- **Pinned context rows:** BTC and ETH sit at the top of the classification table, visually separated, with a "Market context" label.
- **Zero-fee badge:** a small "0 fee" chip next to the symbol, shown only when MEXC returns fee fields equal to 0.
- **Market movers:** two compact side-by-side lists below the Signals panel (Gainers | Losers, 10 rows each). Each row shows rank, symbol, UTC-day change % (▲/▼ + colour), price and 24h turnover. Header: "Since 00:00 UTC (05:30 IST)".
- **Status bar:** one compact chip per agent with status dot + text, last run (IST) and next run. Clicking a chip opens a popover with rows, duration and the last error (component + message).
- **Motion:**
  - flash a cell background for ≤ 600 ms on a live price change
  - respect `prefers-reduced-motion`
  - no decorative animation
- **Empty, warming-up and stale states** use a short sentence plus an icon and the next expected update time.
- **Footer notice** is always visible: "Market analysis only — not financial advice."
