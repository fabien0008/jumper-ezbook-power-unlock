#!/usr/bin/env python3
"""Generate benchmark plots from the tracked raw ladder data.
Reads data/ladder_results.txt (6/8/10W) and data/ladder2_results.txt (10/12/15W),
writes PNGs into assets/. Run from the repo root (or pass --repo).
"""
import re, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = os.path.dirname(os.path.abspath(__file__))
if "--repo" in sys.argv:
    REPO = sys.argv[sys.argv.index("--repo") + 1]
DATA = os.path.join(REPO, "data")
ASSETS = os.path.join(REPO, "assets")
os.makedirs(ASSETS, exist_ok=True)

def parse(path):
    rows = {}
    for line in open(path):
        if not line.startswith("RESULT|"):
            continue
        p = line.strip().split("|")
        lvl = int(p[1].replace("W", ""))
        bench = p[2]
        metric = float(re.search(r"=([\d.]+)", p[3]).group(1))
        glx = re.search(r"glxgears=([\d.]+)", p[3])
        pkg = float(re.search(r"pkg=([\d.]+)", p[4]).group(1))
        rows.setdefault(lvl, {})[bench] = dict(metric=metric, pkg=pkg,
            glx=float(glx.group(1)) if glx else None)
    return rows

d1 = parse(os.path.join(DATA, "ladder_results.txt"))    # 6,8,10
d2 = parse(os.path.join(DATA, "ladder2_results.txt"))   # 10,12,15
merged = {6: d1[6], 8: d1[8], 10: d1[10], 12: d2[12], 15: d2[15]}
levels = [6, 8, 10, 12, 15]

# series: (key, bench, label, sub)
series = [
    ("cpu-7zip",   "7-zip (CPU MIPS)",      "metric"),
    ("cpu-x264",   "x264 encode (CPU fps)", "metric"),
    ("gpu-glmark2","glmark2 (GPU score)",   "metric"),
    ("game-openarena","OpenArena (game fps)","metric"),
    ("combined-x264+glxgears","CPU+GPU: encode fps","metric"),
    ("combined-x264+glxgears","CPU+GPU: GPU fps","glx"),
]
def val(lvl, key, sub): return merged[lvl][key][sub]

# ---- Plot 1: normalized performance vs power limit ----
plt.figure(figsize=(8, 5))
for key, label, sub in series:
    base = val(6, key, sub)
    ys = [100.0 * val(l, key, sub) / base for l in levels]
    plt.plot(levels, ys, marker="o", label=label)
plt.axvline(10, color="gray", ls="--", lw=1)
plt.text(10.1, 102, "daily 10W", color="gray", fontsize=8)
plt.xlabel("PL1 power limit (W)"); plt.ylabel("performance (% of 6W stock)")
plt.title("Performance vs sustained power limit (N3450)\nGPU/game scale to ~10-12W; CPU plateaus; 15W backfires on mixed")
plt.grid(alpha=0.3); plt.legend(fontsize=8, loc="upper left"); plt.xticks(levels)
plt.tight_layout(); plt.savefig(os.path.join(ASSETS, "perf_vs_power.png"), dpi=110); plt.close()

# ---- Plot 2: measured package power drawn vs setting ----
plt.figure(figsize=(8, 5))
for key, label, sub in series[:5]:
    ys = [merged[l][key]["pkg"] for l in levels]
    plt.plot(levels, ys, marker="s", label=label.split(" (")[0])
plt.plot(levels, levels, color="black", ls=":", lw=1, label="PL1 setting (y=x)")
plt.xlabel("PL1 power limit setting (W)"); plt.ylabel("measured package power (W, RAPL)")
plt.title("Measured package power drawn at each setting\nCPU-only saturates ~8-9W; GPU/mixed climb to ~13W")
plt.grid(alpha=0.3); plt.legend(fontsize=8, loc="upper left"); plt.xticks(levels)
plt.tight_layout(); plt.savefig(os.path.join(ASSETS, "power_drawn.png"), dpi=110); plt.close()

# ---- Plot 3: before/after bars (6W vs 10W), % gain ----
labels = [s[1] for s in series]
gains = [100.0 * (val(10, k, sub) / val(6, k, sub) - 1) for k, _, sub in series]
plt.figure(figsize=(8, 5))
bars = plt.barh(labels, gains, color="#3a7")
for b, g in zip(bars, gains):
    plt.text(b.get_width() + 1, b.get_y() + b.get_height()/2, f"+{g:.0f}%", va="center", fontsize=9)
plt.xlabel("performance gain, 6W stock -> 10W unlocked (%)")
plt.title("Real-world gain from the unlock (6W -> 10W)")
plt.grid(axis="x", alpha=0.3); plt.xlim(0, max(gains) * 1.18)
plt.tight_layout(); plt.savefig(os.path.join(ASSETS, "before_after.png"), dpi=110); plt.close()

print("wrote perf_vs_power.png, power_drawn.png, before_after.png to", ASSETS)
