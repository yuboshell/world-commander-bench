#!/usr/bin/env python
"""Generate embodiment.html — the standalone E3 (embodiment/desk) report page.

    python scripts/build_desk_report.py

Reads outputs/desk.json (from scripts/run_desk.py), renders the success-vs-window
frontier, and writes a self-contained embodiment.html (image embedded as base64) at
the repo root. Sibling to report.html (E1) and sc2.html (E2); cross-linked by a nav.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arena import viz   # noqa: E402

NAV = ('<div class="nav">Environments: '
       '<a href="index.html">Grid Arena (E1)</a> &middot; '
       '<a href="sc2.html">StarCraft II (E2)</a> &middot; '
       '<b>Embodiment (E3)</b></div>')

CSS = """
body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;max-width:880px;
margin:2rem auto;padding:0 1rem;color:#222;line-height:1.5}
h1{font-size:1.5rem} h2{font-size:1.15rem;margin-top:1.6rem}
img{width:100%;border:1px solid #e2e2e2;border-radius:6px}
table{border-collapse:collapse;margin:.6rem 0} td,th{border:1px solid #ddd;padding:4px 12px;text-align:left}
.nav{font-size:.9rem;color:#666;border-bottom:1px solid #eee;padding-bottom:.6rem;margin-bottom:1rem}
.nav a{color:#36c} .hint{color:#666;font-size:.92rem}
"""


def main() -> None:
    repo = Path(__file__).resolve().parent.parent
    outdir = repo / "outputs"
    d = json.loads((outdir / "desk.json").read_text())
    png = viz.plot_desk_frontier(d, outdir / "desk_frontier.png")
    uri = viz._data_uri_from_file(png)
    drows = "".join(f"<tr><td>{c['window_ms']:.0f} ms</td><td>{c['success_rate']:.2f}</td></tr>"
                    for c in d["frontier"])
    video = ""
    if (repo / "desk_demo.mp4").exists():
        video = ('<h2>Demo</h2>\n<video controls muted playsinline preload="metadata" '
                 'style="width:100%;border:1px solid #e2e2e2;border-radius:6px">'
                 '<source src="desk_demo.mp4" type="video/mp4"></video>\n'
                 '<p class="hint">A button lights; the LLM grounds the reference; the hand '
                 'reaches and presses — in time when decide+reach &le; the window W, and '
                 'misses when W is too short (round 3). Illustrative; numbers mirror the L0 run.</p>')
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>World Commander — Embodiment (E3) report</title>
<style>{CSS}</style></head>
<body>
{NAV}
<h1>Embodiment (E3) — commanding a body under a clock</h1>
<p class="hint"><b>Updated:</b> {time.strftime('%Y-%m-%d, %I:%M %p %Z')} &middot; members-only</p>
<p>A third World Commander environment. A character sits at a desk; a button <b>lights</b>
for a window <i>W</i> and must be pressed before it goes dark. The command refers to the lit
button (by "lit", colour, or side); the LLM <b>executor</b> grounds the reference to a button;
pressing is a <b>timed reach</b> (distance / hand speed). Success requires both:
the executor grounds correctly <i>and</i> <code>parse+ground latency + reach time &le; W</code>.
So unlike E1/E2, <b>physical execution time</b> is part of the budget — the embodiment axis.
The human supplies intent; the LLM only grounds the reference and never plans the reach
(it hands off execution to the motion layer).</p>

{video}

<h2>Success vs lit window</h2>
<img src="{uri}" alt="E3 success vs lit window">

<h2>Results — {d['model']}, {d['rounds']} rounds, {d['n_buttons']} buttons (L0)</h2>
<p>Executor grounding <b>{d['grounding_accuracy']:.2f}</b>; parse+ground p50
<b>{d['parse_ground_p50_ms']:.0f} ms</b>; reach p50 <b>{d['reach_p50_ms']:.0f} ms</b>.</p>
<table><tr><th>lit window W</th><th>success</th></tr>
{drows}</table>
<p class="hint">At short windows the <b>reach</b> (not the LLM) binds — success climbs to the
grounding ceiling as W grows. The E3 analog of the arena's deadline frontier, now with an
embodied execution term. L0 is pure-Python (a reach-time model, no renderer); higher fidelity
(2D arm; a text-to-motion model as the fast layer) is future work. Parse+ground latency is small
here because the prompt is tiny and the output is one word — consistent with the arena finding
that output length, not input context, dominates latency.</p>
</body></html>"""
    (repo / "embodiment.html").write_text(html)
    print(f"wrote {repo / 'embodiment.html'} ({len(html)} bytes)")


if __name__ == "__main__":
    main()
