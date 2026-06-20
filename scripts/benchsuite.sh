#!/bin/bash
# Run the benchmark suite at the CURRENT power limit (set by caller).
# Usage: benchsuite.sh <label>   (energy_uj must be world-readable)
# Emits one "RESULT|..." line per benchmark, parseable.
LABEL="$1"
EJ=/sys/class/powercap/intel-rapl:0/energy_uj
TZ=/sys/class/thermal/thermal_zone0/temp
GT=/sys/class/drm/card1/gt_act_freq_mhz
CF=/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq
# com_crashed 0 suppresses the "use safe video settings?" dialog so runs are fully automatic
OAFLAGS="+set r_fullscreen 1 +set r_mode -1 +set r_customwidth 1280 +set r_customheight 720 +set sv_pure 0 +set com_crashed 0"

samp_start(){ : >/tmp/samp.$$; ( while :; do echo "$(cat $TZ) $(cat $GT) $(cat $CF)" >>/tmp/samp.$$; sleep 0.5; done ) & SAMP=$!; }
samp_stop(){ kill $SAMP 2>/dev/null; }

# cooldown between benchmarks: let the tail settle, then idle until pkg temp drops (cap ~40s)
cooldown(){ sleep 6; for i in $(seq 1 40); do [ "$(cat $TZ)" -lt 55000 ] && break; sleep 1; done;
  echo "  (cooldown done: temp $(awk -v t=$(cat $TZ) 'BEGIN{printf "%.0f",t/1000}')C)" >&2; }

emit(){ # $1 name  $2 metric_label  $3 metric_value  (uses timing globals)
  local pw tmax gavg cavg dur
  pw=$(awk -v a=$E1 -v b=$E2 -v x=$T1 -v y=$T2 'BEGIN{printf "%.2f",(b-a)/1e6/(y-x)}')
  tmax=$(awk '{if($1>m)m=$1}END{printf "%.0f",m/1000}' /tmp/samp.$$)
  gavg=$(awk '{s+=$2;n++}END{if(n)printf "%.0f",s/n}' /tmp/samp.$$)
  cavg=$(awk '{s+=$3;n++}END{if(n)printf "%.0f",s/n/1000}' /tmp/samp.$$)
  dur=$(awk -v x=$T1 -v y=$T2 'BEGIN{printf "%.1f",y-x}')
  echo "RESULT|$LABEL|$1|$2=$3|pkg=${pw}W|cpu=${cavg}MHz|gpu=${gavg}MHz|tmax=${tmax}C|dur=${dur}s"
}
start(){ samp_start; E1=$(cat $EJ); T1=$(date +%s.%N); }
stop(){ T2=$(date +%s.%N); E2=$(cat $EJ); samp_stop; }

# 1) CPU: 7-zip compression benchmark (MIPS)
cooldown; start; 7z b -mmt4 >/tmp/b.out 2>&1; stop
emit "cpu-7zip" "MIPS" "$(grep -E '^Tot:' /tmp/b.out | tail -1 | awk '{print $NF}')"

# 2) CPU: x264 1080p-ish encode (frames/sec, higher=better)
cooldown; start; ffmpeg -nostats -loglevel error -f lavfi -i testsrc2=size=1280x720:rate=30 \
   -frames:v 1800 -c:v libx264 -preset slow -threads 4 -f null - >/tmp/b.out 2>&1; stop
emit "cpu-x264" "fps" "$(awk -v x=$T1 -v y=$T2 'BEGIN{printf "%.1f",1800/(y-x)}')"

# 3) GPU: glmark2 (composite score), onscreen fullscreen, fixed scene subset
cooldown; start; glmark2 --fullscreen -b build -b texture -b shading -b bump -b refract -b conditionals \
   >/tmp/b.out 2>&1; stop
emit "gpu-glmark2" "score" "$(grep -E 'glmark2 Score' /tmp/b.out | awk '{print $NF}')"

# 4) GAME: OpenArena timedemo (fps)
cooldown
( openarena $OAFLAGS +set com_maxfps 0 +set timedemo 1 +demo benchdemo >/tmp/oa.out 2>&1 ) &
OAP=$!; start
for i in $(seq 1 90); do grep -qE '[0-9]+ frames.*seconds' /tmp/oa.out && break; sleep 1; done
stop; kill -TERM $OAP 2>/dev/null; sleep 3; pkill -9 openarena 2>/dev/null
emit "game-openarena" "fps" "$(grep -oE '[0-9]+ frames [0-9.]+ seconds [0-9.]+ fps' /tmp/oa.out | tail -1 | awk '{print $5}')"

# 5) COMBINED: x264 encode WHILE glxgears loads the GPU (CPU fps under GPU contention)
cooldown
vblank_mode=0 DISPLAY=:0 glxgears -fullscreen >/tmp/gg.out 2>&1 & GG=$!
sleep 2; start
ffmpeg -nostats -loglevel error -f lavfi -i testsrc2=size=1280x720:rate=30 \
   -frames:v 1200 -c:v libx264 -preset slow -threads 4 -f null - >/tmp/b.out 2>&1; stop
kill $GG 2>/dev/null
ggfps=$(grep -oE '[0-9]+ frames in [0-9.]+ seconds = [0-9.]+ FPS' /tmp/gg.out | tail -1 | awk '{print $7}')
emit "combined-x264+glxgears" "encfps" "$(awk -v x=$T1 -v y=$T2 'BEGIN{printf "%.1f",1200/(y-x)}')(glxgears=${ggfps:-?})"
rm -f /tmp/samp.$$
