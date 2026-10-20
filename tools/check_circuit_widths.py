"""
Validate the bus widths of a saved Logisim .circ file.

Logisim reports a width conflict as "Incompatible widths (n)".  This script
reproduces that check on the file that is actually on disk, so a mistake in
the generator cannot slip through.

A net may only carry one bus width.  The classic trap is a Counter's `data`
port: it is as wide as the counter, so tying it to a 1-bit Ground is an error
even though the value is never used (the `load` input is tied low).

Usage:  python3 tools/check_circuit_widths.py [path-to-.circ]
"""
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from circgeom import COMPONENTS, DEFAULT_WIDTHS, GATE_NAMES, gate_geometry

WIDTH_FIXED = {
    "Hex Digit Display": 4,
    "LED": 1,
    "Buzzer": 1,
    "Clock": 1,
}


def parse(path):
    """Return (components, wires) from a .circ file."""
    text = open(path).read()
    comps = []
    for m in re.finditer(r"<comp\s+([^>]*?)(/>|>(.*?)</comp>)", text, re.S):
        head, body = m.group(1), (m.group(3) or "")
        attrs = dict(re.findall(r'name="([^"]*)" val="([^"]*)"', body))
        lib = re.search(r'lib="([^"]*)"', head)
        name = re.search(r'name="([^"]*)"', head)
        loc = re.search(r'loc="\(([^)]*)\)"', head)
        comps.append({
            "lib": lib.group(1) if lib else "",
            "name": name.group(1) if name else "",
            "loc": loc.group(1) if loc else "",
            "attrs": attrs,
        })
    wires = []
    for m in re.finditer(r'<wire from="\(([^)]*)\)" to="\(([^)]*)\)"/>', text):
        a = tuple(int(v) for v in m.group(1).split(","))
        b = tuple(int(v) for v in m.group(2).split(","))
        wires.append((a, b))
    return comps, wires


def port_widths(comp):
    """{port name: (dx, dy, width)} for one component."""
    name, attrs = comp["name"], comp["attrs"]
    if name in GATE_NAMES.values():
        kind = next(k for k, v in GATE_NAMES.items() if v == name)
        geo = gate_geometry(kind, int(attrs.get("inputs", 2)))
    elif name in COMPONENTS:
        geo = COMPONENTS[name]
    else:
        return {}
    out = {}
    for pname, (dx, dy, width) in geo["ports"].items():
        if width == "w":
            if name == "Bit Extender":
                key = "in_width" if pname == "in" else "out_width"
                width = int(attrs.get(key, "8"))
            elif name in WIDTH_FIXED:
                width = WIDTH_FIXED[name]
            else:
                width = int(attrs.get("width", DEFAULT_WIDTHS.get(name, 1)))
        out[pname] = (dx, dy, width)
    return out


def check(path):
    comps, wires = parse(path)

    at_point = defaultdict(list)
    for comp in comps:
        x, y = (int(v) for v in comp["loc"].split(","))
        for pname, (dx, dy, width) in port_widths(comp).items():
            at_point[(x + dx, y + dy)].append((comp["name"], pname, width, comp["loc"]))

    parent = {}

    def find(pt):
        parent.setdefault(pt, pt)
        while parent[pt] != pt:
            parent[pt] = parent[parent[pt]]
            pt = parent[pt]
        return pt

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a, b in wires:
        union(a, b)
        if a[0] == b[0]:
            for y in range(min(a[1], b[1]), max(a[1], b[1]) + 1):
                union(a, (a[0], y))
        else:
            for x in range(min(a[0], b[0]), max(a[0], b[0]) + 1):
                union((x, a[1]), b)

    nets = defaultdict(list)
    for point, ports in at_point.items():
        nets[find(point)].extend((point,) + p for p in ports)

    conflicts = []
    for members in nets.values():
        widths = {m[3] for m in members}
        if len(widths) > 1:
            detail = ", ".join(
                f"{name}.{pname}={width}" for _pt, name, pname, width, _loc in members)
            conflicts.append(f"widths {sorted(widths)}: {detail}")

    print(f"{os.path.basename(path)}: {len(comps)} components, {len(wires)} wires, "
          f"{len(nets)} nets")
    if conflicts:
        print(f"  {len(conflicts)} width conflict(s):")
        for c in conflicts:
            print("   -", c)
    else:
        print("  OK: every net carries a single bus width (Logisim: no "
              "\"Incompatible widths\" error)")
    return conflicts


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else \
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "circuit", "volcano_monitor.circ")
    sys.exit(1 if check(target) else 0)
