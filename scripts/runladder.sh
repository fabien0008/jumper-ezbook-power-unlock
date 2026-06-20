#!/bin/bash
cd ~/bios_work
OUT=~/bios_work/ladder_results.txt; : > $OUT
for pair in "6W:0x00008f0000dd8600" "8W:0x00008f0000dd8800" "10W:0x00008f0000dd8a00"; do
  lbl=${pair%%:*}; val=${pair##*:}
  echo "startit" | sudo -S python3 mmio_rapl.py $val >/dev/null 2>&1
  echo "=== set PL1=$lbl ($val); settling 8s ===" | tee -a $OUT
  sleep 8
  bash benchsuite.sh "$lbl" 2>/dev/null | grep "RESULT|" | tee -a $OUT
done
# restore daily setting: 10W
echo "startit" | sudo -S python3 mmio_rapl.py 0x00008f0000dd8a00 >/dev/null 2>&1
echo "=== LADDER DONE ===" | tee -a $OUT
