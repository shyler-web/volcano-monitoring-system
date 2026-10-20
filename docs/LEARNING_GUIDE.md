# Learning Guide - Volcano Monitoring System

Everything you need to understand this project, in one short document.
Read this before you touch the code.

---

## 1. What the project actually does

A volcano monitoring station has **four sensors**:

| Sensor | Name | Unit | What it measures |
|---|---|---|---|
| `VIB` | Ground vibration | index 0-255 | how hard the ground is shaking |
| `TMP` | Temperature | degC | how hot the ground / gases are |
| `GAS` | Gas concentration | ppm | how much volcanic gas is in the air |
| `ACT` | Volcanic activity | index 0-255 | the overall activity level |

Each reading is put into one of **three warning levels**:

```
NORMAL   value <  WATCH threshold
WATCH    WATCH threshold <= value <  DANGER threshold
DANGER   value >= DANGER threshold
```

The **thresholds** (the one table everybody shares):

| Sensor | WATCH | DANGER |
|---|---|---|
| `VIB` | 40 | 70 |
| `TMP` | 60 | 85 |
| `GAS` | 100 | 180 |
| `ACT` | 50 | 80 |

The project has **two halves** that answer the same question in different ways:

* **Hardware (Logisim)** - a digital circuit that watches the *current* sample live.
* **Software (x86-64 assembly)** - a program that analyses a *recorded* sequence of
  samples and writes a final warning report.

Both halves use the **same thresholds** (`asm/thresholds.inc`), so they can never
disagree about what "danger" means.

---

## 2. Run it

```bash
# 1. build the assembly program
make

# 2. run it on the recorded eruption data
./out/volcano_report data/sensor_readings.csv

# 3. run every automated check (circuit + program)
make check
```

The program prints the report and also saves it to `out/volcano_report.txt`.

**Open the circuit:** start Logisim-Evolution, then *File -> Open* and pick
`circuit/volcano_monitor.circ`. (Or from a terminal:
`~/tools/logisim-evolution/bin/logisim-evolution circuit/volcano_monitor.circ`.)

---

## 3. The Logisim half - the pieces you need to know

Logisim is a **digital circuit simulator**: you drop components on a canvas, wire
them together, and Logisim simulates the result in real time.

The components this project uses:

| Component | Library | What it does here |
|---|---|---|
| **Pin** (input) | Wiring | a sensor value coming in, 8 bits wide |
| **Pin** (output) | Wiring | a result leaving the circuit, for the test bench |
| **Constant** | Wiring | a fixed number - this is where a threshold lives |
| **Tunnel** | Wiring | a **net label**. Two tunnels with the same name are the same wire, without drawing a long cable |
| **Comparator** | Arithmetic | compares two numbers, gives `>`, `=` and `<` outputs |
| **NOT Gate** | Gates | inverts one bit |
| **AND Gate** | Gates | combines two bits |
| **OR Gate** | Gates | combines two bits |
| **Adder** | Arithmetic | adds numbers (we use it to count how many sensors are in danger) |
| **Bit Extender** | Wiring | widens a 1-bit value into a 4-bit number so the adder can use it |
| **Counter** | Memory | counts clock ticks; used for the "abnormal readings in the time window" |
| **Clock** | Wiring | the heartbeat that drives the counters |
| **LED** | I/O | shows the state: green = normal, yellow = watch, red = danger |
| **Hex Digit Display** | I/O | shows a number (danger count, abnormal count) |
| **Buzzer** | I/O - Extra | the emergency siren |
| **Ground** / **Power** | Wiring | constant 0 and constant 1 |

### 3.1 How one sensor channel works

For sensor `VIB` with thresholds 40 and 70:

```
  VIB (8-bit pin)
       |
       |--- Comparator 1 :  VIB  vs  Constant 40   ->  "less than 40?"
       |--- Comparator 2 :  VIB  vs  Constant 70   ->  "less than 70?"
                                    |
                        NOT  <------+  ==>  VIB >= 40   (the WATCH flag)
                        NOT  <------+  ==>  VIB >= 70   (the DANGER flag)
```

**The trick to know:** Logisim's Comparator has three outputs but no ">=" output.
`value >= threshold` is the same as `NOT (value < threshold)`, so we take the
`<` output and invert it with a NOT gate. That way the numbers in the schematic
are the *real* thresholds (40, 70, ...) and not a "threshold minus one".

### 3.2 The severity code - two bits, three levels

Each channel produces two flags, `watch` and `danger`. Because the DANGER
threshold is always higher than the WATCH threshold, `danger` implies `watch`,
so two bits are enough:

| watch | danger | Meaning |
|---|---|---|
| 0 | 0 | NORMAL |
| 0 | 1 | DANGER (also counted as watch) |
| 1 | 0 | WATCH |

The three LEDs are driven straight from those two bits:

* green  = `NOT watch`
* yellow = `watch AND NOT danger`
* red    = `danger`

### 3.3 The global block

* Two **OR trees** reduce the four watch flags to `WANY` and the four danger
  flags to `DANY` (that is the "system status").
* An **adder chain** sums the four danger flags into a 4-bit count (0 to 4).
  Each 1-bit flag is first widened to 4 bits with a **Bit Extender**.
* A **Comparator** checks `danger count >= 2` -> that is the **emergency alarm**
  (the buzzer and the orange LED). "Two or more sensors in danger" is exactly
  the "multiple sensor conditions" the assignment asks for.
* A **Counter** (`CNT_WINDOW`) counts clock ticks from 0 to 8. Its `carry`
  output pulses once every window and clears the second **Counter**
  (`CNT_ABNORMAL`), which counts the ticks where at least one sensor was
  abnormal. That is the "number of abnormal readings within a time window".

### 3.4 Tunnels - why the schematic is readable

Instead of one enormous cable across the canvas, the design uses **tunnels**.
A tunnel is a small labelled arrow; every tunnel with the same label belongs to
the same net. Look for these names:

| Tunnel name | Meaning |
|---|---|
| `SVIB`, `STMP`, `SGAS`, `SACT` | the raw sensor values |
| `WVIB`, `WTMP`, `WGAS`, `WACT` | the per-sensor WATCH flags |
| `DVIB`, `DTMP`, `DGAS`, `DACT` | the per-sensor DANGER flags |
| `WANY`, `DANY` | the system-wide watch / danger flags |
| `DCNT` | number of sensors currently in danger |
| `ABN` | abnormal readings inside the current window |
| `WINC`, `WEND` | window tick counter and window-end pulse |
| `CLK`, `EMERG` | the clock signal and the emergency signal |

---

## 4. The x86-64 assembly half - the pieces you need to know

### 4.1 The rules of the game

* The program is assembled by **NASM** and linked with `ld`. It has **no libc** -
  it talks to the kernel directly.
* A **syscall** is how a program asks the kernel to do something. NASM syntax:

```nasm
    mov     rax, 1              ; syscall number
    mov     rdi, 1              ; argument 1
    mov     rsi, buffer         ; argument 2
    mov     rdx, length        ; argument 3
    syscall
```

The syscalls used here:

| Number | Name | Used for |
|---|---|---|
| 2 | `open` | open the CSV file |
| 0 | `read` | read it into a buffer |
| 1 | `write` | print the report / save it |
| 3 | `close` | close the file |
| 60 | `exit` | quit the program |

* **Registers** (x86-64 calling convention):

| Register | Role in this program |
|---|---|
| `rax` | the value being calculated, or the syscall number |
| `rdi`, `rsi`, `rdx`, `rcx` | the first four syscall arguments |
| `r12` | cursor into the file buffer |
| `r13` | how many bytes were read |
| `r14` | the sensor index (0 to 3) |
| `r15` | one past the last byte of data |
| `rbx` | points at the current sensor's statistics block |

* **Memory layout** (`.bss` section):

```
filebuf   64 KB   the raw CSV text
outbuf    16 KB   the report we are building
numbuf    24 B    scratch space for number -> text conversion
vals      4 x 8B  the four readings of the current row
stats     4 x 64B one 64 byte block per sensor:
                +0  minimum      +8  maximum     +16 sum
                +24 sample count +32 watch count +40 danger count
```

### 4.2 How the program works, step by step

1. **Read the file.** `open` it, `read` it into `filebuf`, `close` it.
2. **Skip the header line.** The first line (`vibration,temp_c,gas_ppm,activity`)
   is not data.
3. **Parse loop.** For every following line: read four numbers separated by
   commas, then fold them into the statistics.

```nasm
.parse_row:
    cmp     r12, r15          ; are we past the end of the data?
    jae     .parse_done
    call    parse_number       ; vibration
    mov     [vals], rax
    call    skip_separator     ; skip the ','
    call    parse_number       ; temperature
    mov     [vals + 8], rax
    ...
    call    update_stats       ; fold the row into the statistics
    call    skip_line          ; jump to the next line
    jmp     .parse_row
```

`parse_number` is the classic "text to integer" loop - multiply the accumulator
by 10 and add the next digit:

```nasm
.digit:
    movzx   rdx, byte [r12]
    sub     edx, '0'
    imul    rax, rax, 10       ; accumulator *= 10
    add     rax, rdx           ; accumulator += digit
    inc     r12               ; next character
    ...
```

4. **Update the statistics.** For each of the four sensors: update min, max,
   sum, sample count, and the two threshold counters.
5. **Build the report.** Text is appended to `outbuf` with two small helpers:
   `emit_str` (append a string) and `emit_number` (append a number, by
   repeatedly dividing by 10 and taking the remainder).
6. **Output it.** `write` it to stdout (fd 1) and to `out/volcano_report.txt`.

### 4.3 The three "gotchas" that cost the most time

* **`lea` only allows scale factors 1, 2, 4 and 8.** `lea rax, [stats + rbx*64]`
  does **not** assemble. Use `mov rdx, rbx; shl rdx, 6; lea rax, [stats + rdx]`.
* **A pointer is not a length.** `cmp r12, r13` compares an *address* with a
  *count*, which is always "past the end". Compare the cursor with the end
  pointer in `r15` instead.
* **NASM reads `0644` as decimal 644, not octal!** `0644` is `0o1204`, which is
  why a file created with `mov edx, 0644` came out with the wrong permissions.
  Write `0o644` (or `420`) when you mean octal.

---

## 5. How the two halves are checked

| Check | What it proves |
|---|---|
| `make check` step 1 | the Logisim circuit answers all 18 test vectors correctly |
| `make check` step 3 | the assembly report matches an independent python model built from the same thresholds |

The python model lives in `tools/gen_vectors.py`. It is the **third** independent
implementation of the same rules (circuit, assembly, python), which is why we
trust the thresholds.

---

## 6. Where everything is

```
circuit/volcano_monitor.circ          the Logisim circuit
circuit/volcano_monitor_vectors.txt   the test vectors
asm/volcano_report.asm                the x86-64 assembly program
asm/thresholds.inc                    the shared thresholds
data/sensor_readings.csv              the recorded eruption data
data/sensor_readings_quiet.csv        a quiet recording (for contrast)
out/volcano_report.txt                the generated report
tools/gen_vectors.py                  reference model + test vector generator
tools/build_volcano_circ.py           generates the Logisim circuit (via MCP)
tools/cross_check.py                  compares the program with the model
docs/PROJECT_REPORT.md                the written project report
```

---

## 7. A five minute demo

1. `make run` - show the report for the eruption data (status = DANGER, alarm raised).
2. `./out/volcano_report data/sensor_readings_quiet.csv` - show the contrast (status = NORMAL).
3. Open `circuit/volcano_monitor.circ` in Logisim. Poke the `VIB` pin above 40
   and watch the yellow LED light up; above 70 the red LED and the buzzer.
4. Open the *Simulation* tab, tick the clock, and watch `HEX_WINDOW` count the
   window and `HEX_ABNORMAL` count the abnormal readings inside it.
