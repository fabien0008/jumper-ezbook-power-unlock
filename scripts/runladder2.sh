#!/bin/bash
# Phase-2 ladder: 10/12/15 W. Requires the MSR to be UNLOCKED (boot service
# disabled + rebooted). For each level we set BOTH the MMIO limit and the MSR
# (unlocked) and keep a root daemon re-asserting the MSR so GPU activity can't
# reset it. 10W is repeated as a cross-check against the phase-1 (locked) result.
cd ~/bios_work
OUT=~/bios_work/ladder2_results.txt; : > $OUT
FLAG=/tmp/reassert.flag
echo "startit" | sudo -S chmod a+r /sys/class/powercap/intel-rapl:0/energy_uj
for pair in "10W:0x00008f0000dd8a00" "12W:0x00008f0000dd8c00" "15W:0x00008f0000dd8f00"; do
  lbl=${pair%%:*}; val=${pair##*:}
  echo "startit" | sudo -S python3 mmio_rapl.py $val >/dev/null 2>&1     # MMIO = level
  touch $FLAG
  echo "startit" | sudo -S python3 reassert_msr.py $val $FLAG >/dev/null 2>&1 &  # root daemon holds MSR
  echo "=== set PL1=$lbl ($val) + MSR re-assert; settling 8s ===" | tee -a $OUT
  sleep 8
  bash benchsuite.sh "$lbl" 2>/dev/null | grep "RESULT|" | tee -a $OUT
  rm -f $FLAG                                                            # stops the daemon
  sleep 3
done
echo "=== LADDER2 DONE ===" | tee -a $OUT
echo "NOTE: re-enable daily 10W lock with: sudo systemctl enable --now ezbook-power-limit.service"
