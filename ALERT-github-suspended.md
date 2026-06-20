# ⚠️ GitHub account suspended (action needed)

**When:** during the overnight autonomous run, 2026-06-20 (~01:1x MDT).

**What happened:** `git push` to `DreamSoul-AI/world-commander-bench` failed with:

> ERROR: Your account is suspended. Please visit https://support.github.com for more information.

This is **account-level** (affects the `yubohuangai` GitHub account / its access),
not a single-repo problem. I cannot resolve it — **you need to contact GitHub
Support** to find out why and get it reinstated.

**Impact:**
- No data is lost. All work is committed **locally**; commits are piling up ahead
  of `origin`. One `git push` (per repo) will sync everything once reinstated.
- The published report (GitHub Pages, the unlisted link) is **not updating** while
  suspended — the live page is stale at the last successful publish.
- I stopped pushing/publishing to avoid hammering GitHub during the suspension. I
  keep committing locally and try a single push each loop iteration to detect when
  access returns; on success I resume normal push + publish.

**Possible cause (guess):** the overnight loop pushed frequently and created/updated
a public Pages repo with an opaque slug; automated activity can trip GitHub abuse
detection. Worth mentioning to Support.

**To resume after reinstatement:**
```
cd /mnt/yubo/github/world-commander-bench && git push origin main
cd /mnt/yubo/github/world-commander && git push origin main   # research repo, if ahead
bash scripts/publish_report.sh                                 # republish the report
```
