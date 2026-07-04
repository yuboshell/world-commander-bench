"""Build a per-game metadata index of the merged SC2EGSet zip.

Streams the single 138 GB (uncompressed) JSON member sequentially and slices
records at the byte offsets from the bundled offsets file — the zip is never
extracted. One CSV row per game: enough to stratify or filter (by map,
matchup, duration, era) without touching the big JSON again.

Resumable: progress is checkpointed every --checkpoint records; rerunning
appends from the last completed record. Single-threaded on purpose (an
overnight, low-power task).

Usage:
  python scripts/build_egset_index.py \
      --zip ~/datasets/sc2/SC2EGSet/sc2egset_merged.zip \
      --out ~/datasets/sc2/SC2EGSet/games_index.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import zipfile

MEMBER = "sc2egset_merged/sc2egset_merged.json"
OFFSETS = "sc2egset_merged/sc2egset_merged_offsets.json"
GAME_LOOPS_PER_SEC = 22.4  # Faster game speed, the ladder/tournament standard

FIELDS = [
    "idx", "offset", "bytes", "map_name", "game_version", "base_build",
    "elapsed_loops", "duration_s", "time_utc",
    "n_game_events", "n_tracker_events", "n_message_events",
    "races", "results", "err",
]


def player_summary(rec: dict) -> tuple[str, str]:
    """Best-effort per-player race/result summary from ToonPlayerDescMap."""
    toon = rec.get("ToonPlayerDescMap") or {}
    races, results = [], []
    for _, desc in sorted(toon.items()):
        if isinstance(desc, dict):
            races.append(str(desc.get("AssignedRace", desc.get("race", "?"))))
            results.append(str(desc.get("Result", desc.get("result", "?"))))
    return "|".join(races), "|".join(results)


def index_row(i: int, off: int, raw: bytes) -> dict:
    row: dict = {"idx": i, "offset": off, "bytes": len(raw), "err": ""}
    try:
        rec = json.loads(raw.decode("utf-8").rstrip().rstrip(","))
        md = rec.get("metadata") or {}
        hdr = rec.get("header") or {}
        det = rec.get("details") or {}
        loops = hdr.get("elapsedGameLoops") or 0
        races, results = player_summary(rec)
        row.update(
            map_name=md.get("mapName", ""),
            game_version=md.get("gameVersion", ""),
            base_build=md.get("baseBuild", ""),
            elapsed_loops=loops,
            duration_s=round(loops / GAME_LOOPS_PER_SEC, 1),
            time_utc=det.get("timeUTC", ""),
            n_game_events=len(rec.get("gameEvents") or []),
            n_tracker_events=len(rec.get("trackerEvents") or []),
            n_message_events=len(rec.get("messageEvents") or []),
            races=races,
            results=results,
        )
    except Exception as e:  # malformed record: keep the row, mark the error
        row["err"] = f"{type(e).__name__}: {e}"[:120]
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--checkpoint", type=int, default=200)
    ap.add_argument("--limit", type=int, default=0, help="index only the first N (0 = all)")
    args = ap.parse_args()

    zp = zipfile.ZipFile(os.path.expanduser(args.zip))
    offsets = json.load(zp.open(OFFSETS))
    total_bytes = zp.getinfo(MEMBER).file_size
    bounds = offsets + [total_bytes]
    n = len(offsets) if not args.limit else min(args.limit, len(offsets))

    out = os.path.expanduser(args.out)
    done = 0
    if os.path.exists(out):  # resume: count completed data rows
        with open(out, newline="", encoding="utf-8") as f:
            done = max(0, sum(1 for _ in f) - 1)
    mode = "a" if done else "w"

    f = zp.open(MEMBER)
    # sequential skip to the resume point (ZipExtFile.seek decompresses through)
    f.seek(bounds[done])

    t0 = time.time()
    with open(out, mode, newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if mode == "w":
            w.writeheader()
        for i in range(done, n):
            raw = f.read(bounds[i + 1] - bounds[i])
            w.writerow(index_row(i, bounds[i], raw))
            if (i + 1) % args.checkpoint == 0:
                fh.flush()
                rate = (i + 1 - done) / max(time.time() - t0, 1e-9)
                eta_min = (n - i - 1) / max(rate, 1e-9) / 60
                print(f"[egset-index] {i + 1}/{n} rows | {rate:.1f} rec/s | ~{eta_min:.0f} min left",
                      flush=True)
    print(f"[egset-index] DONE {n} rows -> {out} in {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    sys.exit(main())
