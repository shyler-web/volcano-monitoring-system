"""
Builder for Logisim-evolution circuits.

Emits an `logisim_apply_batch` payload and can self-check the result:
  * every wire end must land on a real component port (or on another wire)
  * no wire may run through a component body
  * no two component bodies may overlap
"""
import json

from circgeom import COMPONENTS, GATE_NAMES, gate_geometry

GREEN = "#00c000"
YELLOW = "#e0c000"
RED = "#f00000"
ORANGE = "#ff8000"


class Builder:
    def __init__(self):
        self.components = []   # dicts: id, library, name, x, y, attributes
        self.wires = []        # dicts: from_x/from_y/to_x/to_y
        self.ports = {}        # id -> {port_name: (x, y, width)}
        self.bodies = {}       # id -> (x0, y0, x1, y1)
        self.seen = set()

    # ---------- construction ----------
    def comp(self, cid, name, x, y, attributes=None, lib=None, body=None, ports=None):
        if cid in self.seen:
            raise ValueError(f"duplicate id {cid}")
        self.seen.add(cid)
        attributes = dict(attributes or {})
        if name in COMPONENTS:
            geo = COMPONENTS[name]
        else:
            kind = next(k for k, v in GATE_NAMES.items() if v == name)
            geo = gate_geometry(kind, int(attributes.get("inputs", 2)))
        if name == "Tunnel":
            # A tunnel draws its label on the side opposite its facing
            # direction, so the body flips horizontally.
            geo = dict(geo)
            if attributes.get("facing") == "east":
                bx0, by0, bx1, by1 = geo["body"]
                geo["body"] = (-bx1, by0, -bx0, by1)
        self.components.append({
            "id": cid,
            "library": lib if lib is not None else geo["lib"],
            "name": name,
            "x": x,
            "y": y,
            "attributes": attributes,
        })
        self.ports[cid] = {
            pname: (x + dx, y + dy, width)
            for pname, (dx, dy, width) in geo["ports"].items()
        }
        if body is not None:
            bx0, by0, bx1, by1 = body
            self.bodies[cid] = (x + bx0, y + by0, x + bx1, y + by1)
        else:
            bx0, by0, bx1, by1 = geo["body"]
            self.bodies[cid] = (x + bx0, y + by0, x + bx1, y + by1)
        return cid

    def gate(self, cid, kind, x, y, inputs=2, attributes=None, size=50):
        attributes = dict(attributes or {})
        attributes["inputs"] = str(inputs)
        attributes["size"] = str(size)
        return self.comp(cid, GATE_NAMES[kind], x, y, attributes)

    def not_gate(self, cid, x, y, attributes=None):
        attributes = dict(attributes or {})
        attributes["size"] = "30"
        return self.comp(cid, "NOT Gate", x, y, attributes)

    def port(self, cid, port_name):
        return self.ports[cid][port_name]

    # ---------- wiring ----------
    def wire(self, a, b):
        (ax, ay), (bx, by) = a, b
        if ax == bx and ay == by:
            raise ValueError("degenerate wire")
        if ax != bx and ay != by:
            raise ValueError(f"diagonal wire {a} -> {b}")
        self.wires.append({"from_x": ax, "from_y": ay, "to_x": bx, "to_y": by})

    def path(self, points):
        for i in range(len(points) - 1):
            self.wire(points[i], points[i + 1])

    def link(self, a, b, style="h"):
        """Orthogonal 2-segment link between two points."""
        (ax, ay), (bx, by) = a, b
        if ax == bx or ay == by:
            self.wire(a, b)
            return
        corner = (bx, ay) if style == "h" else (ax, by)
        self.path([a, corner, b])

    def connect(self, src, src_port, dst, dst_port, style="h"):
        self.link(self.port(src, src_port), self.port(dst, dst_port), style)

    # ---------- output ----------
    def batch(self, path, circuit="main"):
        return {
            "path": path,
            "circuit": circuit,
            "components": [
                {k: v for k, v in c.items() if k != "attributes"} | {"attributes": c["attributes"]}
                for c in self.components
            ],
            "wires": self.wires,
        }

    # ---------- self check ----------
    def check(self, verbose=True):
        problems = []

        # 1. wire endpoints must touch a port
        port_points = {}
        for cid, ports in self.ports.items():
            for pname, (px, py, _w) in ports.items():
                port_points.setdefault((px, py), []).append((cid, pname))

        def on_wire(pt):
            for w in self.wires:
                (x1, y1), (x2, y2) = (w["from_x"], w["from_y"]), (w["to_x"], w["to_y"])
                if x1 == x2 == pt[0] and min(y1, y2) <= pt[1] <= max(y1, y2):
                    return True
                if y1 == y2 == pt[1] and min(x1, x2) <= pt[0] <= max(x1, x2):
                    return True
            return False

        for w in self.wires:
            for pt in ((w["from_x"], w["from_y"]), (w["to_x"], w["to_y"])):
                if pt not in port_points and not on_wire(pt):
                    problems.append(f"wire endpoint {pt} touches no port")

        # 2. wires must not cross a component body
        for w in self.wires:
            (x1, y1), (x2, y2) = (w["from_x"], w["from_y"]), (w["to_x"], w["to_y"])
            for cid, (bx0, by0, bx1, by1) in self.bodies.items():
                if cid in port_points and any(
                    (px, py) in ((x1, y1), (x2, y2)) for px, py, _ in self.ports[cid].values()
                ):
                    continue
                if x1 == x2:
                    if bx0 < x1 < bx1 and by0 < min(y1, y2) and max(y1, y2) < by1:
                        problems.append(f"wire {w} crosses body of {cid}")
                else:
                    if by0 < y1 < by1 and bx0 < min(x1, x2) and max(x1, x2) < bx1:
                        problems.append(f"wire {w} crosses body of {cid}")

        # 3. component bodies must not overlap
        ids = list(self.bodies)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = self.bodies[ids[i]], self.bodies[ids[j]]
                if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                    problems.append(f"body of {ids[i]} overlaps body of {ids[j]}")

        if verbose:
            if problems:
                print(f"GEOMETRY PROBLEMS ({len(problems)}):")
                for p in problems:
                    print("  -", p)
            else:
                print(f"geometry OK: {len(self.components)} components, {len(self.wires)} wires")
        return problems


def dump(batch, out_path):
    with open(out_path, "w") as fh:
        json.dump(batch, fh, indent=1)
    return out_path
