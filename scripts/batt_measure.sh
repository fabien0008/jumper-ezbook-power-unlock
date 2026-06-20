#!/bin/bash
# Independent power cross-check: battery discharge (total system) vs RAPL (package)
# under a heavy CPU+GPU load at 6W vs 10W PL1 caps. Run on battery (AC unplugged).
B=/sys/class/power_supply/BAT0/power_now
EJ=/sys/class/powercap/intel-rapl:0/energy_uj
echo "startit" | sudo -S chmod a+r $EJ 2>/dev/null
OUT=~/bios_work/batt_results.txt; : > $OUT

samp_batt(){ s=0;n=0; for i in $(seq 1 $1); do s=$((s+$(cat $B))); n=$((n+1)); sleep 2; done; echo $s $n; }

phase(){ # $1=label  ($2 already-running load); samples battery + RAPL over same window
  local e1 t1 e2 t2 bn rapl batt
  e1=$(cat $EJ); t1=$(date +%s.%N)
  read bs bn < <(samp_batt 8)      # ~16s
  e2=$(cat $EJ); t2=$(date +%s.%N)
  batt=$(awk -v s=$bs -v n=$bn 'BEGIN{printf "%.2f",s/n/1e6}')
  rapl=$(awk -v a=$e1 -v b=$e2 -v x=$t1 -v y=$t2 'BEGIN{printf "%.2f",(b-a)/1e6/(y-x)}')
  echo "$1 | system(battery)=${batt}W | RAPL_package=${rapl}W" | tee -a $OUT
}

start_load(){ vblank_mode=0 DISPLAY=:0 glxgears -fullscreen >/tmp/bgg.log 2>&1 & GGP=$!
  stress-ng --cpu 4 --timeout 75s >/dev/null 2>&1 & STP=$!; }
stop_load(){ kill $GGP 2>/dev/null; pkill -9 glxgears 2>/dev/null; wait $STP 2>/dev/null; }

# idle baseline
read bs bn < <(samp_batt 6); echo "idle | system(battery)=$(awk -v s=$bs -v n=$bn 'BEGIN{printf "%.2f",s/n/1e6}')W" | tee -a $OUT

# 6W cap
echo "startit" | sudo -S python3 ~/bios_work/mmio_rapl.py 0x00008f0000dd8600 >/dev/null 2>&1
start_load; sleep 38; phase "load @ 6W cap"; stop_load; sleep 6

# 10W cap
echo "startit" | sudo -S python3 ~/bios_work/mmio_rapl.py 0x00008f0000dd8a00 >/dev/null 2>&1
start_load; sleep 38; phase "load @ 10W cap"; stop_load

# restore daily 10W
echo "startit" | sudo -S python3 ~/bios_work/mmio_rapl.py 0x00008f0000dd8a00 >/dev/null 2>&1
echo "=== BATT DONE ===" | tee -a $OUT
