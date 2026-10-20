"""
Geometry model for Logisim-evolution 4.0.0 components.

Every port offset and body box below was read out of the Logisim-evolution
v4.0.0 sources (com/cburch/logisim/...), so the generator and the checker
agree with what Logisim itself will draw.

Port tuples are (dx, dy) relative to the component anchor.
Body tuples are (x0, y0, x1, y1) relative to the component anchor.
"""

WIRING = "0"
GATES = "1"
PLEXERS = "2"
ARITHMETIC = "3"
MEMORY = "4"
IO = "5"
IO_EXTRA = "10"


def _gate_inputs(n, size=50):
    """Input y-offsets of a Logisim gate, port 0 is the topmost input."""
    if n <= 3:
        if size < 40:
            skip_start, skip_dist, skip_lower_even = -5, 10, 10
        else:
            skip_start, skip_dist, skip_lower_even = -10, 20, 20
    elif n == 4 and size >= 60:
        skip_start, skip_dist, skip_lower_even = -5, 20, 0
    else:
        skip_start, skip_dist, skip_lower_even = -5, 10, 10

    offsets = []
    for index in range(n):
        if n & 1:
            dy = skip_start * (n - 1) + skip_dist * index
        else:
            dy = skip_start * n + skip_dist * index
            if index >= n // 2:
                dy += skip_lower_even
            if n == 4 and size >= 60:
                dy -= 10
        offsets.append(dy)
    return offsets


# name -> {"lib":..., "ports": {port_id: (dx,dy,width)}, "body": (x0,y0,x1,y1)}
COMPONENTS = {
    "Pin": {
        "lib": WIRING,
        "ports": {"port": (0, 0, "w")},
        "body": (-40, -10, 0, 10),
    },
    "Tunnel": {
        "lib": WIRING,
        "ports": {"port": (0, 0, "w")},
        "body": (0, -9, 40, 9),
    },
    "Constant": {
        "lib": WIRING,
        "ports": {"out": (0, 0, "w")},
        "body": (-34, -8, 0, 8),
    },
    "Probe": {
        "lib": WIRING,
        "ports": {"port": (0, 0, "w")},
        "body": (0, -10, 30, 10),
    },
    "Ground": {
        "lib": WIRING,
        "ports": {"out": (0, 0, "w")},
        "body": (-8, 2, 8, 16),
    },
    "Power": {
        "lib": WIRING,
        "ports": {"out": (0, 0, "w")},
        "body": (-8, -16, 8, -2),
    },
    "Clock": {
        "lib": WIRING,
        "ports": {"out": (0, 0, "w")},
        "body": (-40, -10, 0, 10),
    },
    "Bit Extender": {
        "lib": WIRING,
        "ports": {"out": (0, 0, "w"), "in": (-40, 0, "w")},
        "body": (-40, -10, 0, 10),
    },
    "NOT Gate": {
        "lib": GATES,
        "ports": {"out": (0, 0, "w"), "in": (-30, 0, "w")},
        "body": (-30, -9, 0, 9),
    },
    "Comparator": {
        "lib": ARITHMETIC,
        "ports": {
            "in0": (-40, -10, "w"),
            "in1": (-40, 10, "w"),
            "gt": (0, -10, 1),
            "eq": (0, 0, 1),
            "lt": (0, 10, 1),
        },
        "body": (-40, -20, 0, 20),
    },
    "Adder": {
        "lib": ARITHMETIC,
        "ports": {
            "a": (-40, -10, "w"),
            "b": (-40, 10, "w"),
            "sum": (0, 0, "w"),
            "cin": (-20, -20, 1),
            "cout": (-20, 20, 1),
        },
        "body": (-40, -20, 0, 20),
    },
    "Counter": {
        "lib": MEMORY,
        "ports": {
            "q": (0, 0, "w"),
            "data": (-30, 0, "w"),
            "clock": (-20, 20, 1),
            "clear": (-10, 20, 1),
            "load": (-30, -10, 1),
            "updown": (-20, -20, 1),
            "enable": (-30, 10, 1),
            "carry": (0, 10, 1),
        },
        "body": (-30, -20, 0, 20),
    },
    "LED": {
        "lib": IO,
        "ports": {"in": (0, 0, 1)},
        "body": (0, -10, 20, 10),
    },
    "Hex Digit Display": {
        "lib": IO,
        "ports": {"hex": (0, 0, 4)},
        "body": (-15, -60, 25, 60),
    },
    "Buzzer": {
        "lib": IO_EXTRA,
        "ports": {"enable": (0, 0, 1)},
        "body": (-20, -20, 20, 20),
    },
}


def gate_geometry(kind, inputs, size=50):
    """Port/body geometry for a Logisim gate (AND/OR/XOR/NAND/NOR/XNOR)."""
    extra = 10 if kind in ("XOR", "XNOR") else 0
    axis = size + extra
    offsets = _gate_inputs(inputs, size)
    ports = {"out": (0, 0, "w")}
    for i, dy in enumerate(offsets):
        ports[f"in{i}"] = (-axis, dy, "w")
    half = 25 if size >= 40 else 15
    return {"lib": GATES, "ports": ports, "body": (-axis, -half, 0, half)}


GATE_NAMES = {
    "AND": "AND Gate",
    "OR": "OR Gate",
    "XOR": "XOR Gate",
    "NAND": "NAND Gate",
    "NOR": "NOR Gate",
    "XNOR": "XNOR Gate",
}
