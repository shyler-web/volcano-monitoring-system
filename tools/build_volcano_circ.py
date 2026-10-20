"""
Generates circuit/volcano_monitor.circ - the Volcano Monitoring System.

Design
------
Four sensors (ground vibration, temperature, gas concentration, volcanic
activity) each feed a compare-and-classify channel:

    sensor value ---> Comparator(>= WATCH)  ---> watch flag
                  ---> Comparator(>= DANGER) ---> danger flag

A flag is "value >= threshold", implemented as NOT(comparator "less than"
output).  A channel shows its state on three LEDs (green NORMAL, yellow
WATCH, red DANGER) and publishes two 1-bit nets: <W>name and <D>name.

A global block ORs the four watch nets and the four danger nets, sums the
danger flags into a 0..4 count, raises an emergency when two or more
sensors are in danger, and counts abnormal readings inside a sliding
time window with a clocked counter.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from circbuild import Builder, GREEN, ORANGE, RED, YELLOW

# ---------------------------------------------------------------- thresholds
# Shared with the assembly program (asm/thresholds.inc).
SENSORS = [
    # key   pin label  value net   watch net  danger net  watch  danger
    ("VIB", "VIB", "SVIB", "WVIB", "DVIB", 40, 70),
    ("TMP", "TMP", "STMP", "WTMP", "DTMP", 60, 85),
    ("GAS", "GAS", "SGAS", "WGAS", "DGAS", 100, 180),
    ("ACT", "ACT", "SACT", "WACT", "DACT", 50, 80),
]

WINDOW_TICKS = 8  # sampling intervals per monitoring window


def build():
    b = Builder()

    # ================================================================ channels
    for index, (key, label, vnet, wnet, dnet, watch, danger) in enumerate(SENSORS):
        by = 200 + index * 240
        p = f"{key}"

        # --- sensor input -------------------------------------------------
        b.comp(f"PIN_{p}", "Pin", 120, by, {
            "width": "8", "label": label,
        }, body=(-110, -10, 0, 10))
        b.comp(f"T_{p}_src", "Tunnel", 300, by, {
            "width": "8", "label": vnet,
        })
        b.wire((120, by), (300, by))

        # --- comparators --------------------------------------------------
        b.comp(f"T_{p}_w", "Tunnel", 460, by, {
            "width": "8", "label": vnet, "facing": "east",
        })
        b.comp(f"T_{p}_d", "Tunnel", 460, by + 50, {
            "width": "8", "label": vnet, "facing": "east",
        })
        b.wire((460, by), (540, by))
        b.wire((460, by + 50), (540, by + 50))

        b.comp(f"K_{p}_w", "Constant", 500, by + 20, {
            "width": "8", "value": hex(watch),
        })
        b.comp(f"K_{p}_d", "Constant", 500, by + 70, {
            "width": "8", "value": hex(danger),
        })
        b.wire((500, by + 20), (540, by + 20))
        b.wire((500, by + 70), (540, by + 70))

        b.comp(f"CMP_{p}_w", "Comparator", 580, by + 10, {"mode": "unsigned"})
        b.comp(f"CMP_{p}_d", "Comparator", 580, by + 60, {"mode": "unsigned"})

        # --- "greater or equal" = NOT(less than) ---------------------------
        b.not_gate(f"NOT_{p}_w", 700, by + 20)
        b.not_gate(f"NOT_{p}_d", 700, by + 70)
        b.wire((580, by + 20), (670, by + 20))
        b.wire((580, by + 70), (670, by + 70))

        # --- publish the two channel nets --------------------------------
        b.comp(f"T_{p}_W", "Tunnel", 780, by + 20, {
            "width": "1", "label": wnet, "facing": "east",
        })
        b.comp(f"T_{p}_D", "Tunnel", 780, by + 70, {
            "width": "1", "label": dnet, "facing": "east",
        })
        b.wire((700, by + 20), (780, by + 20))
        b.wire((700, by + 70), (780, by + 70))

        # --- LED status block ---------------------------------------------
        # green  = NOT(watch)
        # yellow = watch AND NOT(danger)
        # red    = danger
        b.comp(f"T_{p}_w2", "Tunnel", 880, by - 20, {
            "width": "1", "label": wnet, "facing": "east",
        })
        b.not_gate(f"NOT_{p}_nw", 960, by - 20)
        b.wire((880, by - 20), (930, by - 20))
        b.comp(f"LED_{p}_G", "LED", 1010, by - 20, {
            "color": GREEN, "label": f"LEDN_{label}",
        })
        b.wire((960, by - 20), (1010, by - 20))

        b.comp(f"T_{p}_w3", "Tunnel", 880, by + 20, {
            "width": "1", "label": wnet, "facing": "east",
        })
        b.gate(f"AND_{p}_y", "AND", 1040, by + 40, inputs=2)
        b.wire((880, by + 20), (990, by + 20))

        b.comp(f"T_{p}_d2", "Tunnel", 880, by + 60, {
            "width": "1", "label": dnet, "facing": "east",
        })
        b.not_gate(f"NOT_{p}_nd", 960, by + 60)
        b.wire((880, by + 60), (930, by + 60))
        b.wire((960, by + 60), (990, by + 60))

        b.comp(f"LED_{p}_Y", "LED", 1090, by + 40, {
            "color": YELLOW, "label": f"LEDW_{label}",
        })
        b.wire((1040, by + 40), (1090, by + 40))

        b.comp(f"T_{p}_d3", "Tunnel", 880, by + 100, {
            "width": "1", "label": dnet, "facing": "east",
        })
        b.comp(f"LED_{p}_R", "LED", 1010, by + 100, {
            "color": RED, "label": f"LEDD_{label}",
        })
        b.wire((880, by + 100), (1010, by + 100))

    # ========================================================== global block
    def or_tree(prefix, labels, gy, tunnel_x, or_x, out_x, out_tunnel):
        """Two-level OR tree reducing four 1-bit nets to one."""
        ys = [gy - 20, gy + 20, gy + 60, gy + 100]
        for i, (name, y) in enumerate(zip(labels, ys)):
            b.comp(f"T_{prefix}_{i}", "Tunnel", tunnel_x, y, {
                "width": "1", "label": name, "facing": "east",
            })
        b.gate(f"OR_{prefix}_a", "OR", or_x, gy, inputs=2)
        b.gate(f"OR_{prefix}_b", "OR", or_x, gy + 80, inputs=2)
        b.gate(f"OR_{prefix}_c", "OR", or_x + 110, gy + 40, inputs=2)
        b.wire((tunnel_x, gy - 20), (or_x - 50, gy - 20))
        b.wire((tunnel_x, gy + 20), (or_x - 50, gy + 20))
        b.wire((tunnel_x, gy + 60), (or_x - 50, gy + 60))
        b.wire((tunnel_x, gy + 100), (or_x - 50, gy + 100))
        # OR_a out -> OR_c in0
        b.path([(or_x, gy), (or_x + 30, gy), (or_x + 30, gy + 20), (or_x + 60, gy + 20)])
        # OR_b out -> OR_c in1
        b.path([(or_x, gy + 80), (or_x + 30, gy + 80), (or_x + 30, gy + 60), (or_x + 60, gy + 60)])
        b.comp(f"T_{prefix}_out", "Tunnel", out_x, gy + 40, {
            "width": "1", "label": out_tunnel, "facing": "east",
        })
        b.wire((or_x + 110, gy + 40), (out_x, gy + 40))

    watch_labels = [w for _k, _l, _v, w, _d, _wa, _da in SENSORS]
    danger_labels = [d for _k, _l, _v, _w, d, _wa, _da in SENSORS]

    or_tree("W", watch_labels, 1120, 150, 300, 490, "WANY")
    or_tree("D", danger_labels, 1300, 150, 300, 490, "DANY")

    # ------------------------------------------------- global status LEDs
    gy = 1440
    b.comp("T_WANY_led", "Tunnel", 150, gy, {
        "width": "1", "label": "WANY", "facing": "east"})
    b.not_gate("NOT_WANY", 240, gy)
    b.wire((150, gy), (210, gy))
    b.comp("LED_SYS_G", "LED", 300, gy, {
        "color": GREEN, "label": "SYS_NORMAL"})
    b.wire((240, gy), (300, gy))

    b.comp("T_DANY_led", "Tunnel", 150, gy + 40, {
        "width": "1", "label": "DANY", "facing": "east"})
    b.comp("LED_SYS_R", "LED", 300, gy + 40, {
        "color": RED, "label": "SYS_DANGER"})
    b.wire((150, gy + 40), (300, gy + 40))

    b.comp("T_WANY_y", "Tunnel", 150, gy + 80, {
        "width": "1", "label": "WANY", "facing": "east"})
    b.comp("T_DANY_y", "Tunnel", 150, gy + 120, {
        "width": "1", "label": "DANY", "facing": "east"})
    b.not_gate("NOT_DANY", 240, gy + 120)
    b.wire((150, gy + 120), (210, gy + 120))
    b.gate("AND_SYS_Y", "AND", 310, gy + 80, inputs=2)
    b.path([(150, gy + 80), (200, gy + 80), (200, gy + 60), (260, gy + 60)])
    b.path([(240, gy + 120), (250, gy + 120), (250, gy + 100), (260, gy + 100)])
    b.comp("LED_SYS_Y", "LED", 370, gy + 80, {
        "color": YELLOW, "label": "SYS_WATCH"})
    b.wire((310, gy + 80), (370, gy + 80))

    # --------------------------------------------- danger sensor count (0-4)
    gy = 1580
    ext_y = [gy + 60, gy + 100, gy + 180, gy + 220]
    for i, ((key, label, _v, _w, dnet, _wa, _da), y) in enumerate(zip(SENSORS, ext_y)):
        b.comp(f"T_DCNT_{i}", "Tunnel", 150, y, {
            "width": "1", "label": dnet, "facing": "east"})
        b.comp(f"EXT_{key}", "Bit Extender", 250, y, {
            "in_width": "1", "out_width": "4", "type": "zero"})
        b.wire((150, y), (210, y))

    def adder(cid, x, y, a_src, a_port, b_src, b_port, ground_x, ground_y):
        b.comp(cid, "Adder", x, y, {"width": "4"})
        b.comp(f"GND_{cid}", "Ground", ground_x, ground_y)
        b.path([(ground_x, ground_y), (x - 20, ground_y), (x - 20, y - 20)])
        b.connect(a_src, a_port, cid, "a", style="h")
        b.connect(b_src, b_port, cid, "b", style="h")

    # A1 = ext(VIB) + ext(TMP)
    b.path([(250, ext_y[0]), (270, ext_y[0]), (270, ext_y[0] + 10), (300, ext_y[0] + 10)])
    b.path([(250, ext_y[1]), (270, ext_y[1]), (270, ext_y[1] - 10), (300, ext_y[1] - 10)])
    b.comp("ADD1", "Adder", 340, ext_y[0] + 20, {"width": "4"})
    b.comp("GND_ADD1", "Ground", 290, ext_y[0] - 40)
    b.path([(290, ext_y[0] - 40), (320, ext_y[0] - 40), (320, ext_y[0] - 20)])

    # A2 = ext(GAS) + ext(ACT)
    b.path([(250, ext_y[2]), (270, ext_y[2]), (270, ext_y[2] + 10), (300, ext_y[2] + 10)])
    b.path([(250, ext_y[3]), (270, ext_y[3]), (270, ext_y[3] - 10), (300, ext_y[3] - 10)])
    b.comp("ADD2", "Adder", 340, ext_y[2] + 20, {"width": "4"})
    b.comp("GND_ADD2", "Ground", 290, ext_y[2] - 40)
    b.path([(290, ext_y[2] - 40), (320, ext_y[2] - 40), (320, ext_y[2] - 20)])

    # A3 = A1 + A2  -> danger count
    b.path([(340, ext_y[0] + 20), (370, ext_y[0] + 20), (370, gy + 130), (400, gy + 130)])
    b.path([(340, ext_y[2] + 20), (370, ext_y[2] + 20), (370, gy + 150), (400, gy + 150)])
    b.comp("ADD3", "Adder", 440, gy + 140, {"width": "4"})
    b.comp("GND_ADD3", "Ground", 390, gy + 100)
    b.path([(390, gy + 100), (420, gy + 100), (420, gy + 120)])

    b.comp("T_DCNT_OUT", "Tunnel", 520, gy + 140, {
        "width": "4", "label": "DCNT", "facing": "east"})
    b.wire((440, gy + 140), (520, gy + 140))

    b.comp("T_DCNT_HEX", "Tunnel", 560, gy + 140, {
        "width": "4", "label": "DCNT", "facing": "east"})
    b.comp("HEX_DCNT", "Hex Digit Display", 660, gy + 140, {
        "label": "HEX_DANGER_COUNT"})
    b.wire((560, gy + 140), (660, gy + 140))

    # ---------------------------------------------------------- emergency
    gy = 1820
    b.comp("T_EM_IN", "Tunnel", 150, gy, {
        "width": "4", "label": "DCNT", "facing": "east"})
    b.comp("K_TWO", "Constant", 170, gy + 20, {"width": "4", "value": "0x2"})
    b.comp("CMP_EM", "Comparator", 250, gy + 10, {"width": "4", "mode": "unsigned"})
    b.wire((150, gy), (210, gy))
    b.wire((170, gy + 20), (210, gy + 20))
    b.not_gate("NOT_EM", 320, gy + 20)
    b.wire((250, gy + 20), (290, gy + 20))
    b.comp("T_EM", "Tunnel", 400, gy + 20, {
        "width": "1", "label": "EMERG", "facing": "east"})
    b.wire((320, gy + 20), (400, gy + 20))

    b.comp("T_EM_LED", "Tunnel", 150, gy + 60, {
        "width": "1", "label": "EMERG", "facing": "east"})
    b.comp("LED_ALARM", "LED", 300, gy + 60, {
        "color": ORANGE, "label": "ALARM_LED"})
    b.wire((150, gy + 60), (300, gy + 60))

    b.comp("T_EM_BUZ", "Tunnel", 150, gy + 100, {
        "width": "1", "label": "EMERG", "facing": "east"})
    b.comp("BUZZER", "Buzzer", 300, gy + 100, {"label": "SIREN"})
    b.wire((150, gy + 100), (300, gy + 100))

    # ----------------------------------------------- window / abnormal counters
    gy = 2020
    b.comp("CLK", "Clock", 150, gy, {"label": "SAMPLE_CLOCK"})
    b.comp("T_CLK_1", "Tunnel", 200, gy + 80, {
        "width": "1", "label": "CLK"})
    b.path([(150, gy), (170, gy), (170, gy + 80), (200, gy + 80)])

    # window counter: counts to WINDOW_TICKS, its carry marks a window end
    b.comp("C_WIN", "Counter", 350, gy, {
        "width": "4", "max": hex(WINDOW_TICKS), "label": "CNT_WINDOW"})
    b.comp("T_CLK_2", "Tunnel", 280, gy + 40, {
        "width": "1", "label": "CLK", "facing": "east"})
    b.path([(280, gy + 40), (310, gy + 40), (310, gy + 20), (330, gy + 20)])
    b.comp("PWR_CWIN", "Power", 200, gy + 10)
    b.wire((200, gy + 10), (320, gy + 10))
    b.comp("GND_CWIN_LD", "Ground", 250, gy - 40)
    b.path([(250, gy - 40), (285, gy - 40), (285, gy - 10), (320, gy - 10)])
    b.comp("GND_CWIN_UD", "Ground", 250, gy - 70)
    b.path([(250, gy - 70), (305, gy - 70), (305, gy - 20), (330, gy - 20)])
    b.comp("GND_CWIN_DAT", "Ground", 250, gy, {"width": "4"})
    b.wire((250, gy), (320, gy))
    b.comp("GND_CWIN_CLR", "Ground", 340, gy + 60)
    b.wire((340, gy + 60), (340, gy + 20))

    b.comp("T_WINC", "Tunnel", 430, gy - 40, {
        "width": "4", "label": "WINC", "facing": "east"})
    b.path([(350, gy), (370, gy), (370, gy - 40), (430, gy - 40)])
    b.comp("T_WEND", "Tunnel", 470, gy + 180, {
        "width": "1", "label": "WEND", "facing": "east"})
    b.path([(350, gy + 10), (370, gy + 10), (370, gy + 180), (470, gy + 180)])

    # abnormal counter: counts ticks where at least one sensor is abnormal
    b.comp("C_ABN", "Counter", 550, gy, {
        "width": "4", "max": "0xf", "label": "CNT_ABNORMAL"})
    b.comp("T_CLK_3", "Tunnel", 480, gy + 40, {
        "width": "1", "label": "CLK", "facing": "east"})
    b.path([(480, gy + 40), (510, gy + 40), (510, gy + 20), (530, gy + 20)])
    b.comp("T_WANY_EN", "Tunnel", 450, gy + 10, {
        "width": "1", "label": "WANY", "facing": "east"})
    b.wire((450, gy + 10), (520, gy + 10))
    b.comp("GND_CABN_LD", "Ground", 470, gy - 40)
    b.path([(470, gy - 40), (500, gy - 40), (500, gy - 10), (520, gy - 10)])
    b.comp("GND_CABN_UD", "Ground", 470, gy - 70)
    b.path([(470, gy - 70), (510, gy - 70), (510, gy - 20), (530, gy - 20)])
    b.comp("GND_CABN_DAT", "Ground", 470, gy, {"width": "4"})
    b.wire((470, gy), (520, gy))
    b.comp("T_WEND_2", "Tunnel", 450, gy + 240, {
        "width": "1", "label": "WEND", "facing": "east"})
    b.path([(450, gy + 240), (565, gy + 240), (565, gy + 20), (540, gy + 20)])
    b.comp("T_ABN", "Tunnel", 630, gy, {
        "width": "4", "label": "ABN", "facing": "east"})
    b.wire((550, gy), (630, gy))

    # ------------------------------------------------------------- displays
    gy = 2220
    b.comp("T_WINC_HEX", "Tunnel", 150, gy, {
        "width": "4", "label": "WINC", "facing": "east"})
    b.comp("HEX_WINC", "Hex Digit Display", 250, gy, {"label": "HEX_WINDOW"})
    b.wire((150, gy), (250, gy))

    b.comp("T_ABN_HEX", "Tunnel", 150, gy + 120, {
        "width": "4", "label": "ABN", "facing": "east"})
    b.comp("HEX_ABN", "Hex Digit Display", 250, gy + 120, {"label": "HEX_ABNORMAL"})
    b.wire((150, gy + 120), (250, gy + 120))

    # --------------------------------------------------------- output pins
    gy = 2440
    outputs = [
        ("OUT_WATCH", "OUT_WATCH", 1, "WANY"),
        ("OUT_DANGER", "OUT_DANGER", 1, "DANY"),
        ("OUT_EMERG", "OUT_EMERG", 1, "EMERG"),
        ("OUT_DCNT", "OUT_DCNT", 4, "DCNT"),
        ("OUT_ABN", "OUT_ABN", 4, "ABN"),
    ]
    for i, (cid, label, width, net) in enumerate(outputs):
        y = gy + i * 60
        b.comp(f"T_{cid}", "Tunnel", 150, y, {
            "width": str(width), "label": net, "facing": "east"})
        b.comp(cid, "Pin", 250, y, {
            "width": str(width), "type": "output", "label": label,
        }, body=(0, -10, 50, 10))
        b.wire((150, y), (250, y))

    return b


if __name__ == "__main__":
    builder = build()
    problems = builder.check()
    payload = builder.batch("circuit/volcano_monitor.circ")
    os.makedirs(os.path.join(ROOT, "out"), exist_ok=True)
    with open(os.path.join(ROOT, "out/batch.json"), "w") as fh:
        json.dump(payload, fh, indent=1)
    print(f"components={len(builder.components)} wires={len(builder.wires)}")
    sys.exit(1 if problems else 0)
