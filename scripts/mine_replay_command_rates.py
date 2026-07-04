"""Mine per-player command statistics from a replaypack (SC2ReSet).

Turns the "how fast do pros command?" anchor into a measured distribution:
one CSV row per player-game with targeted-command counts and rates, group
addressing, selection and camera activity, and chat volume. Used first on the
DreamHack Atlanta 2022 pack (1,298 replays) for the datasets report.

Usage:
  python scripts/mine_replay_command_rates.py \
      --zip ~/datasets/sc2/SC2ReSet/2022_03_DH_SC2_Masters_Atlanta.zip \
      --workdir ~/datasets/sc2/SC2ReSet/extracted_atlanta \
      --out ~/datasets/sc2/SC2ReSet/atlanta_command_rates.csv

Replays are extracted once into --workdir (kept for reuse); failures are
counted and skipped, never fatal. Resumable: already-indexed replays (by file
hash name) are skipped on rerun.
"""
from __future__ import annotations

import argparse
import csv
import os
import time
import zipfile

import sc2reader

FIELDS = [
    "replay", "map_name", "duration_s", "player", "race", "result",
    "n_commands", "commands_per_min", "n_control_group", "n_selection",
    "n_camera", "n_chat", "err",
]


def mine_one(path: str) -> list[dict]:
    name = os.path.basename(path)
    try:
        r = sc2reader.load_replay(path, load_level=4)
    except Exception as e:
        return [{"replay": name, "err": f"{type(e).__name__}: {e}"[:120]}]

    secs = max(getattr(r.game_length, "seconds", 0), 1)
    by_player: dict[str, dict] = {}
    for p in r.players:
        by_player[p.name] = dict(
            replay=name, map_name=r.map_name, duration_s=secs,
            player=p.name, race=p.play_race, result=p.result,
            n_commands=0, n_control_group=0, n_selection=0, n_camera=0,
            n_chat=0, err="",
        )
    for e in r.events:
        pname = getattr(getattr(e, "player", None), "name", None)
        if pname not in by_player:
            continue
        t = type(e).__name__
        if "CommandEvent" in t and t != "CommandManagerStateEvent":
            by_player[pname]["n_commands"] += 1
        elif "ControlGroupEvent" in t:
            by_player[pname]["n_control_group"] += 1
        elif t == "SelectionEvent":
            by_player[pname]["n_selection"] += 1
        elif t == "CameraEvent":
            by_player[pname]["n_camera"] += 1
    for m in getattr(r, "messages", []):
        pname = getattr(getattr(m, "player", None), "name", None)
        if pname in by_player:
            by_player[pname]["n_chat"] += 1
    for row in by_player.values():
        row["commands_per_min"] = round(60.0 * row["n_commands"] / secs, 1)
    return list(by_player.values())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True)
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    workdir = os.path.expanduser(args.workdir)
    out = os.path.expanduser(args.out)
    os.makedirs(workdir, exist_ok=True)

    zp = zipfile.ZipFile(os.path.expanduser(args.zip))
    members = [n for n in zp.namelist() if n.lower().endswith(".sc2replay")]
    if args.limit:
        members = members[: args.limit]

    done: set[str] = set()
    if os.path.exists(out):
        with open(out, newline="", encoding="utf-8") as f:
            done = {row["replay"] for row in csv.DictReader(f)}
    mode = "a" if done else "w"

    t0 = time.time()
    n_ok = n_fail = 0
    with open(out, mode, newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, restval="")
        if mode == "w":
            w.writeheader()
        for k, m in enumerate(members, 1):
            base = os.path.basename(m)
            if base in done:
                continue
            path = os.path.join(workdir, base)
            if not os.path.exists(path):
                zp.extract(m, workdir)
            rows = mine_one(path)
            for row in rows:
                w.writerow(row)
            if rows and rows[0].get("err"):
                n_fail += 1
            else:
                n_ok += 1
            if k % 100 == 0:
                fh.flush()
                rate = k / max(time.time() - t0, 1e-9)
                print(f"[mine] {k}/{len(members)} | ok {n_ok} fail {n_fail} | "
                      f"{rate:.1f} replays/s | ~{(len(members)-k)/max(rate,1e-9)/60:.0f} min left",
                      flush=True)
    print(f"[mine] DONE {len(members)} replays (ok {n_ok}, fail {n_fail}) -> {out} "
          f"in {(time.time()-t0)/60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
