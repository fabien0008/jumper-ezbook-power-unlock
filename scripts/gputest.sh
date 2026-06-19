#!/bin/bash
# Steady-state combined CPU+GPU load test at a given PL1.
# 4 CPU workers (saturate power budget) + fullscreen GPU load.
# Sample AFTER PL2 burst window (~28s) so we measure PL1 enforcement.
# usage: gputest.sh <label>
LABEL="$1"
GT=/sys/class/drm/card1/gt_act_freq_mhz
EJ=/sys/class/powercap/intel-rapl:0/energy_uj
CF=/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq

vblank_mode=0 glxgears -fullscreen >/tmp/gg.log 2>&1 &
GGPID=$!
stress-ng --cpu 4 --timeout 55s >/dev/null 2>&1 &
STPID=$!
sleep 38   # let PL1 (~28s window) take over

e1=$(cat $EJ); t1=$(date +%s.%N)
gsum=0; csum=0; n=0
for i in $(seq 1 20); do
  gsum=$((gsum+$(cat $GT))); csum=$((csum+$(cat $CF))); n=$((n+1)); sleep 0.5
done
e2=$(cat $EJ); t2=$(date +%s.%N)

kill $GGPID 2>/dev/null; wait $STPID 2>/dev/null; kill $GGPID 2>/dev/null
fps=$(grep -oE "[0-9]+\.[0-9]+ FPS" /tmp/gg.log | tail -1)
awk -v l="$LABEL" -v e1=$e1 -v e2=$e2 -v t1=$t1 -v t2=$t2 -v gs=$gsum -v cs=$csum -v n=$n -v fps="$fps" \
  'BEGIN{printf "[%s] pkg=%.2f W  GPU=%.0f MHz  CPU=%.0f MHz  glxgears=%s\n", l, (e2-e1)/1e6/(t2-t1), gs/n, cs/n/1000, fps}'
