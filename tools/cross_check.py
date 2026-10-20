"""
Cross-check: run the assembly program and compare its report with a python
reference model built from the same thresholds (tools/gen_vectors.py).

Both the circuit and the assembly program must agree with this model.
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_vectors import SENSORS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASETS = ["data/sensor_readings.csv", "data/sensor_readings_quiet.csv"]


def reference(path):
    rows = [l for l in open(path).read().strip().split("\n")[1:] if l.strip()]
    stats = []
    for index, (_k, _l, _v, _w, _d, watch_t, danger_t) in enumerate(SENSORS):
        values = [int(r.split(",")[index]) for r in rows]
        stats.append({
            "min": min(values),
            "max": max(values),
            "sum": sum(values),
            "n": len(values),
            "watch": sum(1 for v in values if v >= watch_t),
            "danger": sum(1 for v in values if v >= danger_t),
            "severity": 2 if max(values) >= danger_t else (1 if max(values) >= watch_t else 0),
        })
    return {
        "stats": stats,
        "watch_total": sum(s["watch"] for s in stats),
        "danger_total": sum(1 for s in stats if s["severity"] == 2),
        "overall": max((s["severity"] for s in stats), default=0),
        "samples": len(rows),
    }


def from_report(text):
    blocks = re.findall(
        r"(?:Ground vibration|Temperature|Gas concentration|Volcanic activity):.*?\n"
        r"  minimum = (\d+)\s+maximum = (\d+)\s+average = (\d+)\.(\d+)\n"
        r"  samples on WATCH\s+= (\d+)\s+samples on DANGER = (\d+)\n"
        r"  final severity = (\w+)",
        text, re.S)
    severity_map = {"NORMAL": 0, "WATCH": 1, "DANGER": 2}
    stats = [{
        "min": int(b[0]), "max": int(b[1]),
        "avg": f"{b[2]}.{b[3]}",
        "watch": int(b[4]), "danger": int(b[5]),
        "severity": severity_map[b[6]],
    } for b in blocks]
    overall_text = re.search(r"OVERALL STATUS  : (\w+)", text).group(1)
    return {
        "stats": stats,
        "watch_total": int(re.search(r"Samples on WATCH or worse: (\d+)", text).group(1)),
        "danger_total": int(re.search(r"Sensors at DANGER: (\d+)", text).group(1)),
        "overall": severity_map[overall_text],
        "samples": int(re.search(r"Recorded samples analysed : (\d+)", text).group(1)),
        "alarm": "EMERGENCY ALARM : RAISED" in text,
    }


def main():
    failures = 0
    for dataset in DATASETS:
        text = subprocess.run([f"{ROOT}/out/volcano_report", dataset],
                              capture_output=True, text=True, timeout=30,
                              cwd=ROOT).stdout
        ref = reference(f"{ROOT}/{dataset}")
        got = from_report(text)
        problems = []
        for index, (r, g) in enumerate(zip(ref["stats"], got["stats"])):
            if r["min"] != g["min"]:
                problems.append(f"sensor {index} min {r['min']} != {g['min']}")
            if r["max"] != g["max"]:
                problems.append(f"sensor {index} max {r['max']} != {g['max']}")
            if r["watch"] != g["watch"]:
                problems.append(f"sensor {index} watch {r['watch']} != {g['watch']}")
            if r["danger"] != g["danger"]:
                problems.append(f"sensor {index} danger {r['danger']} != {g['danger']}")
            if r["severity"] != g["severity"]:
                problems.append(f"sensor {index} severity {r['severity']} != {g['severity']}")
            expected_avg = f"{r['sum'] // r['n']}.{(r['sum'] % r['n']) * 10 // r['n']}"
            if expected_avg != g["avg"]:
                problems.append(f"sensor {index} average {expected_avg} != {g['avg']}")
        if ref["watch_total"] != got["watch_total"]:
            problems.append(f"watch total {ref['watch_total']} != {got['watch_total']}")
        if ref["danger_total"] != got["danger_total"]:
            problems.append(f"danger total {ref['danger_total']} != {got['danger_total']}")
        if ref["overall"] != got["overall"]:
            problems.append(f"overall {ref['overall']} != {got['overall']}")
        if ref["samples"] != got["samples"]:
            problems.append(f"samples {ref['samples']} != {got['samples']}")
        expected_alarm = ref["danger_total"] >= 2
        if expected_alarm != got["alarm"]:
            problems.append(f"alarm {expected_alarm} != {got['alarm']}")

        if problems:
            failures += 1
            print(f"FAIL  {dataset}")
            for p in problems:
                print("      -", p)
        else:
            print(f"PASS  {dataset}  "
                  f"({got['samples']} samples, overall={'NORMAL WATCH DANGER'.split()[got['overall']]}, "
                  f"alarm={'yes' if got['alarm'] else 'no'})")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
