# Hub style conventions

The report hub is a static microsite (private GitLab Pages) with a navbar for
hub-and-spoke navigation across self-contained HTML reports. Two things must be
identical on every page. They are currently enforced by hand in the committed HTML;
**bake them into the build templates** so rebuilds do not drift.

## 1. Navbar (the switcher)

Every page carries the same bar, immediately after `<body>`, current page in `<b>`:

```html
<div style="font-size:.9rem;color:#666;border-bottom:1px solid #eee;padding-bottom:.6rem;margin-bottom:1rem">Reports: <a href="proposal.html">Proposal</a> &middot; <a href="index.html">Grid Arena (E1)</a> &middot; <a href="sc2.html">StarCraft II (E2)</a> &middot; <a href="embodiment.html">Embodiment (E3)</a> &middot; <a href="motion.html">Crowd Motion (E4)</a> &middot; <a href="literature.html">Literature</a></div>
```

- Order: **Proposal · Grid Arena (E1) · StarCraft II (E2) · Embodiment (E3) · Crowd Motion (E4) · Literature**.
- `graph-bpe-motion.html` is a standalone aside: it carries the same bar plus a trailing
  `&middot; <b>Graph-BPE</b>`, but is **not** listed on the other pages' bars.
- The bar has **three sources that must stay in sync**:
  - static committed HTML (sc2.html, motion.html, literature.html, graph-bpe-motion.html, proposal.html),
  - `arena/viz.py` (generates report.html / E1) — already updated,
  - `scripts/build_desk_report.py` (generates embodiment.html / E3) — **`NAV` is STALE**
    (still "Environments: E1-E3"; missing Proposal/E4/Literature). Replace its `NAV`
    with the bar above before the next E3 rebuild.
  - `motion.html` (E4) regenerates from `world-commander-motion/experiments/build_report.py` —
    update the bar there too.

## 2. Update stamp

One line, **immediately after the navbar** (before the title), same on every page:

```html
<p class="hint"><b>Updated:</b> YYYY-MM-DD, H:MM AM/PM MDT &middot; members-only</p>
```

- **Timezone is always MDT** (Edmonton). A report built on an Alliance cluster stamps in
  Eastern (EDT/EST) — convert it: EDT is 2 h ahead of MDT, EST is 2 h ahead of MST.
- Separator is `&middot;` (not a raw `·`); class is `hint`.
- A page with extra build context (e.g. sc2.html's Machine/Game) appends it after another
  `&middot;` on the same line.
- `proposal.html` is a document, not a run: it stamps just a date (no clock time), keyed to
  its last content change.

## Lint

`grep -L 'proposal.html' *.html` should list only files that *are* proposal.html;
every Updated line should read `... MDT &middot;`; no `EDT`/`EST` in a stamp.
