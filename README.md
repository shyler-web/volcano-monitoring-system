# Volcano Monitoring System

**Group 7 - Project and Case Study**

| # | Name | Roll No. |
|---|---|---|
| 1 | Kartik Jayant | B25CM1027 |
| 2 | Amisha Nainwani | B25CM1074 |
| 3 | Tanushree Chandankhede | B25CM1056 |
| 4 | Archi Gupta | B25CM1007 |
| 5 | Kanhaiya Panjiyar | B25CM1026 |
| 6 | Rama Charan | B25CM1030 |

---

## What this repository contains

A simplified digital **volcano monitoring and early-warning system**. It watches four
sensors (ground vibration, temperature, gas concentration, volcanic activity),
classifies every reading as **NORMAL**, **WATCH** or **DANGER**, raises an emergency
alarm when several sensors are dangerous at once, and produces a final warning report.

| Deliverable | Path |
|---|---|
| Logisim digital circuit | `circuit/volcano_monitor.circ` |
| Logisim test vectors (18 cases) | `circuit/volcano_monitor_vectors.txt` |
| x86-64 Assembly program | `asm/volcano_report.asm` |
| Shared thresholds | `asm/thresholds.inc` |
| Recorded sensor data | `data/sensor_readings.csv`, `data/sensor_readings_quiet.csv` |
| Generated warning report | `out/volcano_report.txt` |
| **Learning guide** (start here) | **`docs/LEARNING_GUIDE.md`** |
| Written project report | `docs/PROJECT_REPORT.md` |
| System architecture diagram | `docs/architecture.svg` |

---

## Quick start

```bash
make            # build the assembly program
make run        # run it on the recorded eruption data
make check      # run every automated check (circuit + program)
```

Open the circuit in Logisim-Evolution:

```bash
~/tools/logisim-evolution/bin/logisim-evolution circuit/volcano_monitor.circ
```

---

## How the pieces fit together

```
 four sensors ──► sensor channel (comparator + LEDs)  ──► global decision logic
                        (hardware, live)                        │
                                                                 ├─ system LEDs
                                                                 ├─ emergency LED + buzzer
                                                                 └─ window counters
 recorded CSV ──► x86-64 assembly program ──► final warning report (software)
```

Both halves read the **same threshold table** (`asm/thresholds.inc`), so the hardware
and the software can never disagree about what "danger" means. A third, independent
python model in `tools/gen_vectors.py` is used to check both.

![architecture](docs/architecture.svg)

---

## Current status

```
Logisim circuit : 18 / 18 test vectors pass
Assembly program: output matches the reference model on both datasets
Overall verdict for the recorded eruption : DANGER, emergency alarm RAISED
```

---

## Prerequisites

Before running the project, install:

- **Python 3**
- **NASM 2.16.03** + or a compatible version
-  **GNU ld** and the standard build tools
- Logisim-Evolution 4.0.0 to open and simulate the circuit
- **Logisim MCP server** (`afishyke/Logisim-Evolution-MCP-Server`) - lets an AI
  assistant build, validate and test the `.circ` file directly

Run **make check** to validate the project.