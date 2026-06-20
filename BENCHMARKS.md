# Real-world benchmarks: 6W vs 8W vs 10W

Measured on the Jumper EZbook (Celeron N3450, Apollo Lake, HD 500) with the
unlock applied at three sustained power limits. Each number is a real workload,
not a synthetic power reading.

## Headline: 6W (stock) → 10W (unlocked)

| Benchmark | What it measures | 6W (stock) | 10W (unlocked) | Gain |
|-----------|------------------|-----------:|---------------:|:----:|
| **OpenArena timedemo** | game fps (follow-bot demo, 1280×720) | 69.1 fps | **111.0 fps** | **+61%** |
| **glmark2** | GPU score (GL scenes) | 205 | **310** | **+51%** |
| **7-zip** | CPU compression (MIPS) | 4858 | **6383** | **+31%** |
| **combined glxgears** | GPU fps while CPU encodes | 134 | **257** | **+91%** |
| **combined x264** | CPU encode fps while GPU busy | 15.3 | **18.5** | **+21%** |
| **x264 encode** | CPU video encode fps | 22.6 | 25.6 | +13% |

The biggest wins are **GPU/game and mixed CPU+GPU** workloads — exactly the cases
that used to be strangled at 6W and which the MSR-lock fix unlocked (see the GPU
latch story in the main README, Act 12).

## Full watt ladder

Raw data: [`data/ladder_results.txt`](data/ladder_results.txt). `pkg` = average
package power over the run, `cpu`/`gpu` = average clocks, `tmax` = peak temp.

| Benchmark | metric | 6W | 8W | 10W |
|-----------|--------|---:|---:|----:|
| 7-zip | MIPS | 4858 | 6259 | 6383 |
| x264 encode | fps | 22.6 | 25.6 | 25.6 |
| glmark2 | score | 205 | 263 | 310 |
| OpenArena | fps | 69.1 | 95.2 | 111.0 |
| combined x264 | enc fps | 15.3 | 17.1 | 18.5 |
| combined glxgears | fps | 134 | 207 | 257 |

Measured package power / peak temp at each level (representative):

| Level | CPU bench draw | GPU bench draw | peak temp |
|-------|---------------:|---------------:|----------:|
| 6W | ~6.2–7.0 W | ~6.3–6.4 W | 74 °C |
| 8W | ~7.8–8.4 W | ~8.8–9.3 W | 78 °C |
| 10W | ~7.8–8.9 W | ~11.0–11.3 W | 84 °C |

(TjMax is 105 °C — every run had ≥20 °C of thermal headroom, so results are
power-policy-limited, not thermal.)

## What the curve shows

- **GPU/game workloads scale almost linearly with the limit** (glmark2 +51%,
  OpenArena +61% from 6→10 W) and draw the full budget (11 W at the 10 W setting,
  including PL2 bursts). This is the headline benefit of the fix.
- **CPU-only workloads saturate around 8–9 W.** 7-zip jumps +29% from 6→8 W but
  only +2% more from 8→10 W; x264 is flat 8→10 W. Reason: the all-core turbo
  ratio is capped at 21× ≈ 2.0–2.09 GHz (MSR 0x1AD), and four Goldmont cores at
  that clock only draw ~8–9 W — so beyond ~9 W the CPU is frequency-limited, not
  power-limited. Their `pkg` draw confirms it (7-zip pulls 8.9 W even at the 10 W
  setting, never the full 10 W).
- **Mixed CPU+GPU is where headroom matters most.** With the GPU contending,
  glxgears fps nearly doubled (134→257, +91%) and the simultaneous encode still
  improved +21% — at 6 W the two starve each other down to a shared ~6 W; at 10 W
  they share a 10 W budget.

## Method / reproducibility

- A/B done live without rebooting: the MSR is locked at 10 W, and the PUnit
  enforces `min(MMIO, MSR)`, so setting the **MMIO** limit (`0x70A8`) to 6/8/10 W
  selects the effective cap. `scripts/runladder.sh` drives the three levels;
  `scripts/benchsuite.sh` runs the five benchmarks at the current level.
- **Cooldown** between every benchmark: idle until package temp returns to ≤55 °C
  (idle floor ~52 °C) so each run starts from the same thermal baseline.
- Power = RAPL energy-counter delta over the run wall-time; clocks/temp sampled at
  2 Hz; peak temp reported.
- **OpenArena**: a recorded *follow-bot* demo (camera rides the AI through real
  combat — [`data/openarena-benchdemo.dm_71`](data/openarena-benchdemo.dm_71)),
  replayed with `timedemo 1`. Launched with `+set com_crashed 0` so the
  "safe video settings?" prompt never appears — fully unattended.
- 12 W and 15 W are not shown: the MSR is locked at 10 W for daily use, which caps
  the ladder there. Testing higher needs a reboot (the lock clears on reboot) with
  the boot service temporarily disabled.
