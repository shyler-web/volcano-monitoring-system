#!/usr/bin/env bash
# Full verification for the Volcano Monitoring System.
#
#  1. rebuild the Logisim test vectors from the shared thresholds
#  2. run them against the Logisim circuit
#  3. run the assembly program and compare its report with a python
#     reference model built from the same thresholds
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGISIM="${LOGISIM_EXECUTABLE:-$HOME/tools/logisim-evolution/bin/logisim-evolution}"
cd "$ROOT" || exit 1
fails=0

echo "=============================================================="
echo " 1/3  Logisim test vectors"
echo "=============================================================="
python3 tools/gen_vectors.py > /dev/null || { echo "FAIL: cannot generate vectors"; fails=1; }
out=$("$LOGISIM" --locale en --test-vector main "$ROOT/circuit/volcano_monitor_vectors.txt" \
        "$ROOT/circuit/volcano_monitor.circ" 2>&1)
echo "$out" | tail -2
if echo "$out" | grep -q "Failed: 0"; then
  echo "PASS: Logisim circuit matches every test vector"
else
  echo "FAIL: Logisim test vectors did not all pass"; fails=1
fi

echo
echo "=============================================================="
echo " 1b/3  Circuit bus-width check (Logisim "Incompatible widths")"
echo "=============================================================="
if python3 tools/check_circuit_widths.py; then
  echo "PASS: no bus-width conflict in the saved circuit"
else
  echo "FAIL: the saved circuit has a bus-width conflict"; fails=1
fi

echo
echo "=============================================================="
echo " 2/3  Assembly program output"
echo "=============================================================="
for dataset in data/sensor_readings.csv data/sensor_readings_quiet.csv; do
  ./out/volcano_report "$dataset" > /dev/null 2>&1 || { echo "FAIL: $dataset did not run"; fails=1; }
done
echo "PASS: the program ran on both datasets"

echo
echo "=============================================================="
echo " 3/3  Assembly output vs the python reference model"
echo "=============================================================="
python3 tools/cross_check.py || fails=1

echo
if [ "$fails" -eq 0 ]; then
  echo "ALL CHECKS PASSED"
else
  echo "SOME CHECKS FAILED"
fi
exit "$fails"
