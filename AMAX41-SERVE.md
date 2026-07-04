# amax41 serving task — START HERE (server phase, Milestone 1)

> **For the agent on amax41** (written 2026-07-04 by the yubopc session; Yubo
> relays only a one-line pointer to this file). Bring up the LLM serving side
> on this machine. The game side runs on yubopc (Windows) and connects through
> an SSH tunnel; your job is everything server-local.

Read `SC2.md` ("Run (amax41 — latency only)") and the newest `LOG.md` entry
(2026-07-04 overnight; its "Next (server phase)" paragraph is this task)
before acting.

## Guardrails
- **GPU 2 only** — GPUs 0 and 1 belong to labmates. If GPU 2 is busy with
  someone else's process, stop and report; do not take another GPU.
- Serve on **127.0.0.1**, never 0.0.0.0 — the endpoint must not be exposed
  to the lab network; yubopc reaches it via SSH tunnel.
- Do **not** run StarCraft II here (Linux build caps at 4.10 — useless for
  win-rate; the game runs on yubopc).
- No overnight-style push loops; at most one normal commit/push if you
  change docs.

## Tasks (in order)

1. **Pull.** If the remotes still reflect the June suspension layout
   (GitLab-only), realign per `YUBOPC-SETUP.md` "Hosting note": GitHub
   `yuboshell/world-commander-bench` is canonical as `origin`; GitLab
   `worldcommander/world-commander-bench` stays as mirror remote `gitlab`.

2. **Check `nvidia-smi`** (guardrail above).

3. **Serve** Qwen/Qwen3-4B-AWQ with vLLM on GPU 2, per SC2.md:
   `CUDA_VISIBLE_DEVICES=2`, `--host 127.0.0.1 --port 8001
   --quantization awq --max-model-len 8192 --enforce-eager --dtype half` —
   inside a tmux session named `wc-vllm` so it survives disconnects.

4. **Verify**: `curl 127.0.0.1:8001/v1/models`, then one short timed chat
   completion; note time-to-first-token.

5. **Authorize yubopc for the tunnel**: append the following public key as
   one line to `~/.ssh/authorized_keys` (create `~/.ssh` mode 700 / file
   mode 600 if needed):

   ```
   ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC489mQIes33q6uptPwDpo9LJ9Zxgu49KeedIe3zNejkCH8QgN9ONJ6c0upZErh6cBHnvjDR8xvGR5TaT/WEe4MTuFqBaA2rWGsD0vO379RhpdAsowfVBvruLTn4/kn9NpLJRDyQv/o3aTJ8c/z7RQtEoivzX3PcTrrS22KiVUNpBGdYkU6sARdmOnksBamvJgNjvfIDA7KUJ4ZUYZ3tqGiG+TZI8oVYQ1olfGBstAfWoE72QdXVHV35gSnyrOptI7BU5k66GQWFTZe2gbck0bcrmjVmzMUqk40yRr9/Im36mBy37wBRvM0n4n5q86LSdHhHpWPUYe2ih9rzKQXn+guIDfB/Xm9v71zsegQO8k+8Ts0SF1uXfWAg4/X0FoL2KYfc1AQs2Hv01JnGDNqYL46yeTkfv3EUFP5dqMByfD+JpURAkFLAhy/NfpthfQdLavXZjK7qrHmQbTy3c1fiTVwQnLzGhQ9/HQa8m8l4t6MhWG6nbWKEfg6NafGVeR7XXU= yubo.huang@hotmail.com
   ```

6. **Report back in one summary**: pull result, GPU 2 status, vLLM up (tmux
   session name, VRAM used), `/v1/models` output, the timed completion's
   TTFT, and confirmation the key line is in `authorized_keys`.

After your report, the yubopc session opens the tunnel and runs the first
bounded `2s3z` smoke game against this endpoint with `WCB_SC2_METRICS`
logging — the start of the Milestone-1 server-phase loop.
