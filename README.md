# Unlocking the 6 W power limit on a Jumper EZbook (Celeron N3450 / Apollo Lake)

The full, unedited story of how we raised the **sustained package power limit (PL1)**
on a cheap Jumper EZbook netbook from its factory **6 W** to **10 W** — including
every wrong turn, dead end, premature wrong conclusion, and the experiments that
finally explained why the unlock helps CPU-bound work but **not** anything that
touches the GPU.

> **TL;DR**
> - **What works:** writing the MMIO `PACKAGE_RAPL_LIMIT` register at
>   `MCHBAR(0xFED10000) + 0x70A8`. Sets PL1 to 10 W. Verified: 4-core load went
>   **5.97 W → 10.12 W**, all-core clock **1.5 GHz → 2.09 GHz**, temp 62 → 76 °C
>   (TjMax is 105 °C, so it is policy-limited, not thermal).
> - **What does NOT work:** MSR `0x610` (write sticks but PCODE ignores it), the
>   classic Core MMIO offset `0x59A0`, config-TDP MSRs (`#GP`), the BIOS
>   "Turbo-XE TDP Limit" NVAR byte (set it, rebooted, no effect).
> - **The catch:** the moment the **iGPU does any work**, the PUNIT latches the
>   whole package back to ~6 W and our register is overridden. So the unlock is a
>   **CPU-only win** (compiles, encodes, batch jobs with the screen idle). Browsing
>   in Chrome — which keeps the GPU busy — mostly stays at 6 W.

---

## The machine

- **Jumper EZbook**, Intel **Celeron N3450** (Apollo Lake, Goldmont, 4 cores,
  6 W TDP), 6 GB RAM, Intel HD Graphics 500.
- AMI Aptio UEFI. We already had (from prior sessions) the ability to read/write
  the SPI flash and the AMI `Setup` NVAR variable directly from Linux — see the
  sibling notes on NVAR/SPI tweaking. That earlier work taught us one important
  lesson that turned out to be a recurring theme here:
  **many settings exposed in the BIOS are dead — present in AMI's IFR template
  but never plumbed into the FSP/PCODE by Jumper.** (We proved this for the DVMT
  graphics-memory setting: changing it does nothing.)
- **Base/turbo:** base 1.1 GHz, all-core burst capped at 2.1 GHz, 1-core 2.2 GHz
  (`MSR 0x1AD = 0x15151516`). **TjMax = 105 °C** (`MSR 0x1A2 = 0x690000`).

## The goal

Raise the **sustained** power budget above 6 W so the CPU stops dropping to
~1.5 GHz under prolonged all-core load.

---

## The investigation (in order, dead ends included)

### Act 1 — The obvious lever: RAPL MSR `0x610`. Wrong.

Intel's documented package power limit is `MSR_PKG_POWER_LIMIT` (`0x610`). We
decoded the factory value:

```
0x610 = 0x00008f0000dd8600
  PL1 (sustained) = 0x600 * (1/256 W) = 6.00 W, enabled
  PL2 (burst)     = 0xF00 * (1/256 W) = 15.00 W, enabled
  lock bit63      = 0   (NOT locked -> we can write it)
```

Power unit confirmed from `MSR 0x606 = 0x...08` → `1/256 W`. The kernel's
`powercap` sysfs agreed (`constraint_0_power_limit_uw = 5999616`). We wrote
PL1 = 10 W:

```
0x610 := 0x00008f0000dd8a00   # PL1 raw 0xA00 = 10 W
```

It **read back fine**, powercap showed 10 W… and under a 45 s load the package
still sat at **5.97 W**, cores at 1.5 GHz, with `THERM_STATUS` (`0x19C`) showing
the active power-limit log bit. **PCODE overrides the MSR.** First dead end.

### Act 2 — MMIO mirror at the Core offset `0x59A0`. Dead end (wrong offset).

On Core CPUs the package limit is mirrored in MMIO at `MCHBAR + 0x59A0`, and the
hardware enforces the *lower* of MSR vs MMIO — the trick ThrottleStop/XTU use.
We found MCHBAR from PCI `0:0.0` offset `0x48` = `0xFED10001` → base
**`0xFED10000`**, and read `0xFED159A0`:

```
MMIO @0xFED159A0 = 0x0000000000000000
```

All zeros. We *wrongly* concluded "no MMIO mirror exists." (It does — just not at
the Core offset. See Act 7. This was the mistake that led to a wrong conclusion.)

### Act 3 — Config-TDP MSRs. Dead end (unimplemented).

```
0x648 CONFIG_TDP_NOMINAL : #GP
0x649 CONFIG_TDP_LEVEL1  : #GP
0x64A CONFIG_TDP_LEVEL2  : #GP
0x64B CONFIG_TDP_CONTROL : #GP
```

Apollo Lake simply doesn't implement config-TDP. Dead end.

### Act 4 — VR current limit. Not the limiter.

`MSR 0x601 = 0xa8` ≈ 21 A — far above anything 6 W would need. Not it.

### Act 5 — The BIOS "Turbo-XE TDP Limit" NVAR. Dead end (the reboot test).

The extracted IFR (AMI setup form) had a promising numeric:

```
"TDP Limit"  Help: "Turbo-XE Mode Processor TDP Limit in Watts. 0 means using
             the factory-configured value."   QuestionId 0x69, VarOffset 0xEC
"TDC Limit"  (amps)                            QuestionId 0x68, VarOffset 0xE9
```

So we set NVAR offset `0xEC = 0x0A` (10 W) in **both** redundant Setup stores,
with EIST and Turbo Mode both enabled, and **rebooted to test**. Result after
reboot: still **5.97 W**. No effect. The field is gated behind
`SuppressIf QID 0x352==0` (a "Turbo-XE supported" flag that is 0 on this locked
SKU), so the firmware never feeds `0xEC` to the PUNIT. **Same dead-knob pattern
as DVMT.** Dead end.

### Act 6 — The premature WRONG conclusion.

At this point we wrote it up as *"the 6 W limit is PCODE-locked and cannot be
raised by any lever"* and even saved that to memory. **This was wrong.** It was
based on the Act-2 single-offset MMIO read that returned zeros.

### Act 7 — The pushback, and doing the MMIO check properly.

Prompted by healthy skepticism ("I was quite sure we could do that"), we
re-opened the weakest link: the MMIO read. A *clean* all-zero read is suspicious —
real registers rarely read as pure zero. Two checks:

1. **`CONFIG_STRICT_DEVMEM=y`** in the kernel — but on x86 this still allows
   `mmap` of non-RAM MMIO holes (it fails outright with EPERM if denied; ours
   succeeded). So the read path was legitimate.
2. **Is MCHBAR even live?** We scanned the whole 32 KB MCHBAR window
   (`scripts/mchscan.py`): **764 non-zero dwords**, real data starting at
   `+0x1000`. The window is live. We then searched it for the RAPL-limit
   signature (PL2 word `0x8F00`, the `dd86` pattern):

```
+0x70A8 = 0x00008F0000DD8600   PL1=6.00W PL2=15.00W   <-- FOUND IT
```

**The MMIO package-limit register on Apollo Lake is at `MCHBAR + 0x70A8`, not the
Core `0x59A0`.** It held the *factory* 6 W value, untouched by our MSR write — and
it is what the hardware actually enforces.

### Act 8 — It works.

```
0xFED170A8 := 0x00008F0000DD8A00   # PL1 = 10 W
```

| Metric            | Before (6 W) | After (10 W) |
|-------------------|--------------|--------------|
| Steady-state power| 5.97 W       | **10.12 W**  |
| All-core clock    | ~1.5 GHz     | **2.09 GHz** |
| Package temp      | 62 °C        | 76 °C        |

2.09 GHz is the **all-core ratio ceiling** (21×), so **10 W is the sweet spot** —
going higher (we tried 15 W) adds nothing for all-core CPU, because the limit
becomes frequency (ratio) rather than power.

### Act 9 — "Will raising it more help the GPU?" — methodology error first.

First combined CPU+GPU test gave nonsense (10 W phase drew 14.9 W, 15 W phase
drew 9.9 W). **Bug:** we sampled 8–18 s into the load, which is *inside* the
~28 s PL2 burst window, so both phases were governed by PL2 = 15 W, not PL1.
Lesson: to measure PL1 you must sample **after** the PL1 time window elapses
(>35 s in), exactly like the CPU test.

### Act 10 — The GPU clamp, and why no register fixes it.

With a correct steady-state combined test (4 CPU workers + fullscreen glxgears):

```
[PL1=10W] pkg=5.99 W  GPU=200 MHz  CPU=1195 MHz
[PL1=15W] pkg=5.99 W  GPU=200 MHz  CPU=1195 MHz
```

Both pinned at **6 W** with the CPU forced to ~1.2 GHz — even though the package
limit register still read 10 W and i915 was **not** overwriting it (verified by
reading `0x70A8` before/during/after a GPU load — it stayed 10 W). So a *separate*
limit engages when the GT is active. We hunted it:

- **`+0x7870`** holds a RAPL-format value **PL1 ≈ 6.01 W, enabled** — the likely
  GT-active ceiling. **But it is read-only** (writes don't stick).
- **`+0x70A0`** holds the SoC **TDP = 6 W** (PKG_POWER_INFO). Also **read-only**.
- **Per-plane limit MSRs** PP0/IA `0x638` and PP1/GT `0x640`: **`#GP`** (don't
  exist). Only their energy *counters* (`0x639`, `0x641`) exist.

So when the GPU is active, the enforced package budget = the SoC TDP (6 W), which
is held only in **read-only** registers, configured by PCODE/FSP at boot. No
runtime lever raises it.

### Act 11 — The "latch", and what it means for Chrome.

A per-second trace under pure CPU load (`data/timeseries-cpu-load.txt`) shows the
mechanism precisely:

```
 t  GPUmhz  CPUmhz  pkgW
 1-9   100   2089   ~10.0   GPU idle (RC6) -> 10 W, full turbo
10    300   1392    6.65    GPU wakes -> package collapses
16-30 ~100  ~1450   ~6.0    GPU idle again, but power STAYS at 6 W (sticky)
```

The package runs at 10 W **only while the GPU sits in deep idle (RC6)**. The
instant the GPU does *any* work it drops to 6 W, and it does **not** recover even
when the GPU goes back to 100 MHz moments later. Because Chrome (and any
compositing desktop under real use) keeps waking the GPU, **interactive/browser
use mostly stays at 6 W.** The 10 W win is real for **CPU-bound work with the GPU
genuinely idle**: compiling, video *encoding* (not decoding), compression, batch
processing — ideally on a static screen or over SSH/console.

---

## Final verdict

| Lever | Writable? | Enforced? | Verdict |
|---|---|---|---|
| MSR `0x610` PL1 | yes | no (PCODE overrides) | dead |
| MMIO `0x59A0` (Core offset) | n/a | n/a | wrong offset on Goldmont |
| **MMIO `0x70A8` (package limit)** | **yes** | **yes, GPU idle only** | **WORKS (CPU-only)** |
| MMIO `0x7870` (GT-active ~6 W) | no (read-only) | yes, GPU active | locked |
| MMIO `0x70A0` (SoC TDP 6 W) | no (read-only) | — | locked |
| config-TDP `0x648-0x64C` | — | — | `#GP`, unimplemented |
| PP0/PP1 limit MSRs `0x638/0x640` | — | — | `#GP`, don't exist |
| BIOS NVAR "TDP Limit" `0xEC` | yes (flash) | no | not plumbed (dead knob) |

## Register map (MCHBAR base `0xFED10000`)

| Offset | Meaning | Notes |
|--------|---------|-------|
| `+0x70A0` | PKG_POWER_INFO (TDP) | 6 W, read-only |
| `+0x70A8` | **PACKAGE_RAPL_LIMIT** | the writable lever; `0x00008f0000dd8a00` = PL1 10 W / PL2 15 W |
| `+0x7870` | GT-active package ceiling | ~6 W, read-only |

RAPL limit qword layout: bits `[14:0]` PL1 power (× 1/256 W), bit `15` PL1 enable,
bit `16` clamp, bits `[23:17]` time window, bits `[46:32]` PL2, bit `47` PL2
enable, bit `63` lock.

---

## Usage

Everything needs root (reads/writes `/dev/mem` and MSRs).

```bash
# show current MMIO package limit
sudo ./scripts/mmio_rapl.py

# set PL1 = 10 W now (volatile, lost on reboot)
sudo ./scripts/mmio_rapl.py 0x00008f0000dd8a00

# re-find the register on a different board / firmware
sudo ./scripts/mchscan.py

# generic MCHBAR peek/poke
sudo ./scripts/genpoke.py 70a8                 # read
sudo ./scripts/genpoke.py 70a8 0x...           # write
```

### Make it persistent (systemd)

```bash
sudo install -m 0755 scripts/ezbook-pl1.py /usr/local/sbin/ezbook-pl1.py
sudo install -m 0644 systemd/ezbook-power-limit.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ezbook-power-limit.service
```

`ezbook-pl1.py` is self-contained (no deps) and re-applies PL1 = 10 W on every
boot. Confirm with `systemctl status ezbook-power-limit.service`.

---

## Getting a real boost when the GPU IS active — honest options

You asked how to defeat the GPU→6 W fallback so the boost applies in *all* cases.
The blunt truth from the investigation: **at runtime, you can't.** The GT-active
ceiling is the SoC TDP held in read-only registers and enforced by PCODE. Here is
the honest menu, easiest → hardest:

1. **Keep the GPU asleep for CPU-bound tasks (the practical lever you control).**
   The package stays at 10 W *only* while the iGPU is in RC6. So for jobs where
   CPU matters more than GPU, prevent needless GPU wake-ups:
   - Run the job from a **TTY/SSH with no X/Wayland session** (nothing composites).
   - In Chrome, disable GPU: `--disable-gpu --disable-gpu-compositing` (software
     compositing keeps the iGPU idle; the CPU now has the full 10 W). Trade-off:
     you lose hardware video *decode*, so this is good for CPU-heavy browsing,
     bad for video playback.
   - Use a non-compositing window manager for CPU-bound sessions.
   This doesn't raise the GPU-active ceiling — it keeps more of your workload in
   the 10 W regime by not triggering the policy.

2. **Cap the GPU frequency (mitigation, not a boost).** Under combined load,
   `echo 300 | sudo tee /sys/class/drm/card1/gt_max_freq_mhz` gives the CPU more
   of the shared 6 W. Total stays 6 W — you're just reallocating it. Only worth it
   if your workload is CPU-bound but unavoidably wakes the GPU.

3. **The only real fix: change the SoC TDP in firmware (high effort, real brick
   risk, may be impossible).** The 6 W GT-active budget is set at boot by the FSP
   silicon-init / PCODE. To raise it you'd have to patch the **FSP-S power-limit
   UPD default** (or the PCODE PL config) in the BIOS image and reflash via the
   SPI method. Caveats:
   - If the value lives in **PCODE/microcode** (signed), it is **not patchable** —
     and given Apollo Lake's history this is the likely case.
   - If it lives in an **FSP-S UPD** (unsigned), it is patchable. We already have
     the toolchain (`bios.bin` dump, SPI `/dev/mtd0` write path, UEFITool /
     IFRExtractor) from the NVAR work. This is the open research path; it is the
     same FSP-locked territory that defeated the DVMT setting, so temper
     expectations.

If you only ever do CPU-bound batch work (compiles, transcodes, compression) with
the screen idle, you already have the full win and don't need any of this.

---

## Tools in this repo (`scripts/`)

| Script | Purpose |
|--------|---------|
| `mmio_rapl.py` | show / write the MMIO package RAPL limit at `0x70A8` |
| `mchscan.py` | scan 32 KB MCHBAR for liveness + the RAPL signature (re-find the register) |
| `dumpregs.py` | dump the register region around `0x70A8` and scan for limit-shaped qwords |
| `genpoke.py` | generic MCHBAR qword peek/poke by offset |
| `nvar.py` | read/write the AMI `Setup` NVAR variable in SPI flash (from prior work) |
| `peek.py` | print selected NVAR Setup offsets (EIST/Turbo/TDC/TDP) |
| `gputest.sh` | steady-state combined CPU+GPU load benchmark (samples after PL2 window) |
| `ezbook-pl1.py` | self-contained boot-time applier (used by the systemd unit) |

## Safety notes

- All runtime writes here are **volatile** — a reboot restores the factory 6 W.
  Nothing here modifies flash except `nvar.py` (and we established the NVAR power
  knob does nothing anyway).
- TjMax is 105 °C and we measured ≤76 °C at 10 W sustained, so thermals are not a
  concern at this limit on this chassis. If you push a hotter chip/chassis, watch
  `THERM_STATUS` (`MSR 0x19C`) and the thermal zones.
- `/dev/mem` MMIO pokes are inherently sharp tools. Writing the wrong MCHBAR
  offset can hang the box. The offsets here are specific to **Apollo Lake
  (N3450)**; re-run `mchscan.py` before trusting them on any other silicon.

*Written as a complete lab notebook, dead ends and all, so the next person (or the
next me) doesn't re-walk the wrong paths.*
