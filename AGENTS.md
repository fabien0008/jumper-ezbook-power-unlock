# Agent guide — jumper-ezbook-power-unlock (public write-up only, as of 2026-08-09)

This repo now holds **only the public article** (`README.md`, `BENCHMARKS.md`, `assets/`) — read-only
content for anyone who lands here via search or a shared link. There is nothing runnable left: scripts,
the systemd unit, and raw benchmark data were removed and are mastered in the private `home-infra`
monorepo instead.

**Any technical/runnable work** (new scripts, findings, benchmark data, systemd changes) belongs there:

```bash
git clone https://github.com/fabien0008/home-infra
cd home-infra/hosts/ezbook/tuning
```

Full pre-move history: `git log import/jumper-ezbook-power-unlock` once you've cloned home-infra.

**Editing the article itself** (prose, numbers, images in `README.md`/`BENCHMARKS.md`/`assets/`) is
still done here directly — this repo stays public and live for that purpose.
