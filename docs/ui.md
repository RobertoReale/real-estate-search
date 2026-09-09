# The Interface

This is the map of the dashboard: what it is drawn with, how it is arranged, and where
the next screen goes. It exists because the alternative has a shape, and the shape is
always the same — a feature arrives, nothing says where it belongs, and it becomes one
more collapsible panel above the property grid. That happened here. Three of them, and
they pushed the first property card 1385 px down a 900 px screen before anyone measured
it.

It is a **reference**, not a rulebook and not a second architecture. The rules — a
component names a role and never a colour, a screen composes a primitive and never draws a
control, icons come from the barrel, a failed operation goes to the toast while a failed
read stays where its data would have been — are in
[`conventions.md`](conventions.md), with the enforcement that makes each of them true; the
file to open for a given change, and the regression each of these parts was built out of,
are in [`architecture.md`](architecture.md)'s "Where to Act" map. What is here is the
vocabulary those two are written in: which roles exist and what each one means, which
primitives exist and when to reach for which, what each screen owns, and the question to
ask before adding a tenth.

Values are not repeated here. `frontend/src/styles/tokens.css` holds the numbers,
`frontend/src/ui/` holds the components, and both explain themselves at the point of
definition. This document names things and says what they are for.

---

## 1. Tokens

Three layers, and only the middle one is a vocabulary anybody uses.

1. **The palette** — named ramps in OKLCH: `--clay-*` (neutral), `--azure-*` (accent),
   `--sage-*` / `--ochre-*` / `--garnet-*` (the verdicts), `--harbor-*` (informational),
   and the categorical ramps. Nothing outside `tokens.css` may name a ramp step.
2. **The roles** — what a colour is *for*. `--surface`, `--ink-muted`, `--negative-ink`.
   Written out once for light and again for dark; neither theme is derived from the other.
3. **The utilities** — a Tailwind `@theme inline` block that turns every role into
   `bg-*`, `text-*`, `border-*`, `ring-*`, `fill-*`, `stroke-*`. This is why a component
   writes `bg-surface` and carries no `dark:` variant.

A screen only ever touches layer 3, which is layer 2 spelled as a class.

### The role vocabulary

**Grounds** — where a thing sits, from furthest back to furthest forward.

| Role | It is |
|---|---|
| `page` | the document. Nothing else may use it |
| `surface` | a panel, a card, a dialog — the plane content is written on |
| `raised` | a surface that floats above another one |
| `control` | a control with its own ground *inside* a panel: a select, a segment of a switcher. Not `surface`, which in dark is the panel it sits on |
| `sunken` / `sunken-strong` | a well inside a panel: an inner row, a filled track |
| `overlay` | the scrim behind a dialog or a sheet |
| `console` / `console-ink` | the log viewer, which is a terminal and is allowed to look like one |
| `veil` / `hairline` / `wash` | a scrim under a control floating over a photograph, and the hairline that keeps a map marker readable against a tile of any colour |

**Ink** — five steps, and they are a hierarchy rather than a range to pick from.
`ink` is the page default set on `body`; `ink-strong` / `ink-body` / `ink-muted` /
`ink-dim` are the hierarchy *within* a panel, starting one step softer because a panel
that opens at full strength competes with the page under it. Two more are not part of the
ladder: `ink-faint` is a glyph the user should find but not read (a dismiss ×, a disabled
caret) and `ink-hint` is placeholder text. `on-solid` is the text on a filled control, and
it is the only white in the app.

**Lines** — `line`, `line-subtle`, `line-strong`. A border is the third way to separate
two regions, after space and after a change of ground; reach for it last.

**Accent** — `accent` and its states, `accent-ink` for accent-coloured text, `accent-link`
for a link, `accent-soft` / `accent-tint` / `accent-line` / `accent-ring` for the quieter
uses, `accent-graph` / `accent-graph-point` for a chart. The accent marks **what the user
can act on**. It never says whether a number is good or bad; that is what the three
verdict ramps are for, and keeping the two apart is the whole reason the ramps are
separate.

**Verdicts** — `positive`, `caution`, `negative`, each with at least the same six shapes:
`*-ink` (text), `*-soft` (a chip's ground), `*-tint` (a callout's ground), `*-line`
(its border), `*-dot` (a status dot), and the bare role for a solid fill. A verdict is a
judgement about a fact — an undervalued price, a scraper failing, a listing gone.

**Identity** — `info` (a statement about the data: a drawn area, a zone note),
`neutral`, `tag`, `rent`, `favorite`, and `portal-immobiliare` / `portal-idealista`.
These identify a thing and carry no judgement at all, which is why they are kept out of
the verdict set: nothing should be able to render "Idealista" in the colour that means
"good deal".

**Elevation** — `shadow-e1`, `shadow-e2`, `shadow-e3`, `shadow-accent`. The one place the
two themes are genuinely different *mechanisms* rather than different values: in light a
cast shadow, in dark a lighter surface plus a brighter edge, because a shadow on a dark
ground is invisible.

### Type, space, radius

- **Two faces.** `--font-display` is an old-style serif, scoped to `h1`/`h2` in
  `index.css` and used nowhere else; `--font-sans` is a humanist grotesque and is
  everything else; `--font-mono` is the log and the numbers that must not be read as
  prose. Both chains resolve locally on Windows, macOS and Linux — the browser suite may
  not reach the network, and a webfont arriving late reflows the layout it is measuring.
- **The scale** runs `3xs` → `4xl`. The two smallest steps exist because the app had been
  reaching for `text-[10px]` and `text-[11px]` arbitrary values 39 times; above `base` the
  steps run on a 1.2 ratio with tracking that tightens as the size grows.
- **Space** is a 4 px base, plus three named steps that were being retyped as numbers and
  drifting: `touch` (the fingertip target), `inset` (what a panel keeps from its own
  border) and `gutter`.
- **Radius is named after what it wraps** — `chip`, `control`, `card`, `surface`, `pill` —
  so a control and the card it sits in cannot drift apart the way six near-identical
  buttons did.
- **`tnum`** is a utility, not a base rule: digits that line up in a column must be the
  same width or the eye cannot compare them without reading them. Every price, every
  €/m², every count in a table, every measured number in Insights. Proportional figures
  stay the default inside a sentence, which is most of the app's text.

### What lives in `index.css` instead

`index.css` owns four things that are not tokens: the `body` ground and its two glow
gradients, the display face on `h1`/`h2`, the focus-ring floor under every focusable
element, and the skip link. It also still holds the pre-primitive class set — `.glass`,
`.input`, `.btn-*`, `.chip-*`, `.t-*`, `.panel` — which the screens that have not moved
onto the primitives still use, plus `.defer-offscreen` (the grid's `content-visibility`
windowing) and the Leaflet overrides. Those last two are load-bearing and are not
candidates for tidying: the tile filter is the one `dark:` in the codebase, and the
z-index isolation is what keeps a map from drawing over a dialog.

**A new screen uses the primitives, not those classes.** They are the migration's tail,
and every one of them that goes unreplaced is a second way to draw a thing that already
has one.

---

## 2. Primitives

`frontend/src/ui/` holds seventeen components and one rule: **a primitive knows nothing
about property listings.** A `Button` does not know what it saves; a `Chip` does not know
that garnet means a price drop. The moment a file in there mentions a listing, a portal or
a price it has become a component, and `src/components/` is where it goes. Import from the
barrel (`import { Button, Field } from "../ui"`), never from the files — that is what makes
it obvious in review when a screen reaches past the set for something the set should have.

| Reach for | When |
|---|---|
| `Button` | anything the user presses. `variant` × `tone`, below |
| `IconButton` | a press whose whole label is a picture. `label` is **required**; it is both the accessible name and the tooltip |
| `Chip` | a small tinted **fact**, never a control. It renders a `<span>` and takes no handler — a removable filter chip is a chip with a `Button` beside it |
| `Card` / `CardHeader` | a surface that holds a thing: a listing, a panel, a section of a form. `elevation` says how far forward it sits |
| `Field` | the wiring around a form control — label, hint, error — generated rather than typed at a call site. `Input`, `Select` and `Checkbox` adopt it through context |
| `Input` / `Textarea` | text. 16 px on a phone, or iOS Safari zooms in on focus and never back out |
| `Select` | choosing one of a list, where the popup has to be themed or carry a second line. A **native** `<select>` stays native where the browser suite drives it with `selectOption` |
| `Checkbox` | a box that is ticked, is not, or is neither. The third state is why it is not a native input |
| `Dialog` | a window over the page for something to finish or abandon |
| `Sheet` | the same, arriving from an edge. What a dialog becomes below `sm`, where a centred window wastes a quarter of the screen |
| `Popover` | detail the screen has no room to state, anchored to the control that asked for it. Takes focus, holds paragraphs and links |
| `Tooltip` | a short label for a control whose meaning is not written on it. **Never the only copy of anything** — if it matters, it is a `Popover` |
| `Tabs` | alternative views of one subject. A tab list is a *single* stop in the tab order; the arrow keys move within it |
| `Toast` | the drawing of a transient message. The *deciding* stays in `components/Toast.tsx` |
| `Skeleton` | the shape of something that has not arrived — the box the real content will occupy, so the page does not jump |
| `EmptyState` | nothing here, and what to do about it |
| `ErrorState` | this region could not be loaded, said where its content would have been |

`AppShell` is in the same directory and deliberately **not** in the barrel: the barrel is
the set a screen is drawn *with*, and the shell is what draws the screens.

### Loudness is two axes

`tone` is what a control is about (`neutral`, `accent`, `positive`, `caution`,
`negative`); `variant` is how loudly it says it (`solid`, `outline`, `ghost`). Both
vocabularies live in `ui/tone.ts`, and the pair is a discriminated union rather than two
free props, so a combination with no correct drawing fails `tsc` instead of rendering an
undrawn one. `size` is the third and least interesting axis, and a control that has to
name a fourth is asking for a primitive that does not exist yet.

**Solid is `accent` and `negative` and nothing else.** A filled button is an assertion,
and this product makes exactly two: *do the thing*, and *undo or destroy it*. The narrower
reason is measurable — `--on-solid` is white, and only azure and garnet have a step dark
enough to carry it at 4.5:1 *and* a designed hover a shade darker again.

**Outline is the default.** An action offered rather than urged, and what most of the app
is. **Ghost** is for a control inside something it must not compete with: a card's own
header, a toolbar.

A screen with three outline buttons and one solid one has an answer to "what did you want
me to do here?". A screen with four solid ones does not.

### Empty, loading, error

Every region that fetches has four states and must be able to draw all four: content,
`Skeleton`, `EmptyState`, `ErrorState`. **No surface may render as an unexplained blank
rectangle** — the user cannot tell "no results" from "still loading" from "broken" from
"you have not set this up yet", and the four look identical until something says which.
"Nothing matched" and "nobody answered" are the same blank space and want opposite
reactions, which is why the last two are separate components rather than one with a flag.

An `EmptyState`'s `action` is a **slot**, not an `onClick`: the control belongs to the
caller, carries the caller's `data-action` id, and is inventoried under the name of the
thing it actually does.

---

## 3. Information architecture

### The shell

`ui/AppShell` is the outermost layout route. It mounts once and stays mounted for the
session, which is load-bearing rather than incidental: the event stream is opened there,
and a shell rendered per screen would tear the connection down and reopen it on every
navigation.

It carries what belongs to the session rather than to a screen — what this is, where you
can go, what the scanner is doing, and the theme and language switches. **The navigation
is one element in two shapes**: below `lg` a bar pinned to the bottom where a thumb
reaches, from `lg` up a row in the header where the room is. Rendered twice with one copy
hidden, every destination would sit twice in the tab order and every `data-action` twice
in the page, and the control inventory would be counting renderings instead of controls.
The filter rail makes the same argument in the same way.

### The places

| Route | What it is | Why it is where it is |
|---|---|---|
| `/listings` | the grid, the filter rail, the result header, the batch bar and the map view | The default. Anything unrecognised lands here, so a user with data sees properties before configuration. It holds **no configuration control at all**, and the browser suite fails if one comes back |
| `/listings/:id` | one property: the facts, the benchmarks, the price history, the curation, the provenance, the audit | A route rather than a modal, so it can be linked, bookmarked, opened in a second tab and pointed at from a notification. Nested under the grid, so returning restores the scroll position and the selection |
| `/insights` | what the collection adds up to: scraper health, market velocity, price trends | Its own place. These were three collapsed panels above the grid; a destination whose whole content is three "Show" links is a page that asks to be clicked before it says anything, so they are sections now |
| `/searches` | the searches that go out to the portals — creating, editing, disabling them — then the account-wide health, then the maintenance jobs | Its own place. It is the screen a user spends time on twice, at the start and whenever the market moves, and it was costing every other visit the top of the page |
| `/activity` | the scan, live and afterwards, and the backend log one press further in | Reached from the **header**, not the navigation: a fifth item leaves the Italian labels about 56 px each at 390 px, and "Impostazioni" does not fit in 56 px |
| `/settings` | every setting, in sections | An overlay over the grid |
| `/logs` | the backend log | An overlay over the grid. Also reachable from Activity, which is where the question it answers usually starts |
| `/start` | the guided first run: what the app is, the first search, the first scan | Where `/` leads on an install that has never held a search. A destination rather than a wizard, because a wizard over the app cannot be left half-finished and come back to |
| `/setup` | the capability setup: five optional steps between a first search and one that works | A place for the same reason, plus one more — it is reached from Settings as often as from the guide, so it cannot exist only on the way through |

`/` resolves to one of two addresses depending on whether this install has ever held a
search, and renders nothing while it is still finding out: redirecting on an empty cache
sends every reload to the guide and then snaps back a beat later, which the user reads as
the app not knowing where it is.

### Overlay or destination

Four of those are nested **inside** the listings route (`/listings/:id`, `/settings`,
`/logs`, and the grid itself); the rest sit beside it. The nesting is what lets the
address move between the grid, a property, the settings and the log without re-running the
grid's queries, losing the scroll position or emptying a multi-selection. Insights,
Searches, Activity, the guide and the setup are **not** nested, because a user on them is
not looking at the grid, and a screen drawn over a grid nobody is reading is a grid being
kept alive for nothing.

### State lives in the address

Every filter, the sort, the view and the open property are in the URL, and
`routes/params.ts` is the only thing that reads or writes them. Three rules make an
address worth sharing: nothing at its default is written down, a value the app does not
recognise is dropped, and it round-trips. A new screen with state a user would want to
send someone puts it there too — and adds it to that file, not to a second parser.

### Searching is not filtering

The two verbs are separated by route on purpose, and separating them by route is not
enough on its own: a filter form and a search form still look identical. **A search
(`/searches`) goes out to a portal and collects.** **A filter (`/listings`) narrows what
was already collected.** The empty state is where the distinction is either made or lost,
which is why the grid's is never "no such houses" but always "none among the N collected"
with the way to widen it — and why the way to *go and find more* is a link to the other
screen rather than a control on this one.

---

## 4. Where a new screen goes

In order. The first answer that fits is the answer.

1. **Is it a fact about a property that is already on screen?** Then it is not a screen.
   It goes on the property route — a section, a `Popover` for the detail, a `Chip` for the
   verdict. The card says one thing per subject; a second market-position statement beside
   the first is not more information, it is a contradiction the user has to resolve.

2. **Is it a setting?** Then it is a section in `/settings`, and — if it changes what the
   app *can do* rather than how it behaves — a step in `/setup`. Not a new place. Fifty-four
   fields in one dialog is already the problem `/setup` exists to walk a user through; a
   fifty-fifth somewhere else makes it worse in a new direction.

3. **Is it something the user reads about the collection as a whole?** Then it is a
   section in `/insights`. If it is a chart, it renders with zero, one and two points or it
   does not ship: one point is a reading and not a trend, and a lone point spans no time at
   all, which is a division by zero in every scale that was not written for it
   (`routes/insights/chart.test.ts`).

4. **Is it something the user does to their searches, or a job that repairs the
   collection?** Then it belongs to `/searches`, under the heading that says which of the
   two it is. "Find coordinates" next to a list of searches reads as something a search
   does.

5. **Is it about a run — what the scanner is doing, or did?** Then it is `/activity`.

6. **Only if none of those fit** is it a new destination, and then it must answer three
   questions before it is one. *Is it a place a user goes deliberately, more than once?*
   *Can it be left half-finished and returned to?* *Does the navigation have room for it —*
   which today it does not, at 390 px, which is why Activity is in the header. A "yes, no,
   no" is an overlay nested under the grid, not a fifth tab.

Whatever the answer, it is drawn with the primitives, it names roles and not colours, it
has all four states, every control on it carries a `data-action` id with an entry in
`frontend/e2e/actions.ts`, and it is reachable and operable by keyboard at 390, 768 and
1440 px. None of that is negotiable and none of it is checked by hand — see below.

---

## 5. Responsive, and what enforces all of this

Three widths are tested and they stand for three situations: **390** (a phone in one
hand), **768** (a tablet, and the width where a two-column layout has to decide), and
**1440** (a laptop). Tailwind's `sm` is the phone boundary for type and control sizing;
`lg` (1024 px, `hooks/useMediaQuery.DESKTOP_QUERY`) is where the navigation moves into the
header and the filter rail stops being a sheet.

Whichever mechanism a responsive control uses, it renders **once**. The navigation is one
node repositioned by CSS; the filter rail is genuinely different markup at the two sizes
and so picks one in JavaScript, from `DESKTOP_QUERY`. What neither of them does is render
both and hide one — that is two tab orders and two elements answering to the same
`data-action`.

Nothing in this document is kept true by being written down. Each part of it has a gate:

| This | Is held by |
|---|---|
| roles, never ramp steps or hex; no `dark:` variants | `src/styles/tokens.test.ts` |
| icons from the barrel; no emoji anywhere in the interface, including the dictionaries | `src/ui/icons.test.ts` |
| a combination of `tone` and `variant` that has no correct drawing | `tsc`, via the unions in `ui/tone.ts` |
| every control reachable, operable, and inventoried | `frontend/e2e/` — the coverage spec fails on a handler with no `data-action`, and on an inventory entry with no test that fires it |
| no sideways scroll and no serious `axe-core` violation at 390 / 768 / 1440 | the same suite, on every route |
| a token that moved a card's padding on every screen at once | `npm run e2e:visual` — nine routes × three widths, CI-only |
| what a screen costs to open | `npm run lighthouse` against `frontend/lighthouse/budget.json`, CI-only |

The gates and their expected numbers are listed once, in
[`audit.md` §0](audit.md#0-green-baseline-run-first-every-audit). The rules those gates
enforce, and the regression behind each, are in [`conventions.md`](conventions.md) and
[`invariants.md`](invariants.md).
