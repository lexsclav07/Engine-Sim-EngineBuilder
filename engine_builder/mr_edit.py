"""Find editable numbers in existing engine-sim .mr scripts and write edited clones.

engine-sim scripts are a full language, so instead of understanding them this
finds literal numbers sitting in recognisable spots (named arguments, input
defaults, labels, gears, timing/flow samples) and patches just those
characters. Everything else in the file is copied byte for byte.
"""

import datetime
import os
import re

CLONE_MARK = "// Cloned by Engine Builder"

_TOKEN = re.compile(r'''
    (?P<comment>//[^\n]*|/\*.*?\*/)
  | (?P<string>"(?:[^"\\\n]|\\.)*")
  | (?P<number>(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?)
  | (?P<ident>[A-Za-z_@][A-Za-z0-9_]*)
  | (?P<ws>\s+)
  | (?P<punct>.)
''', re.S | re.X)

_KEYWORDS = {"public", "private", "node", "input", "output", "alias", "import", "label",
             "module", "return", "function"}
_FUNCS = {"k_carb": "cfm (k_carb)", "k_28inH2O": "cfm @28inH2O", "k_32inH2O": "cfm @32inH2O",
          "celcius": "deg C"}
_INT_KEYS = {"steps", "max_sle_solver_steps", "fluid_simulation_steps",
             "rotor_calculation_quality", "rotor_housing_resolution"}
_OPERATORS = {"*", "/", "+", "-", "."}


class Tok:
    __slots__ = ("kind", "text", "start", "end", "line")

    def __init__(self, kind, text, start, end, line):
        self.kind, self.text, self.start, self.end, self.line = kind, text, start, end, line


def tokenize(text):
    toks, line = [], 1
    for m in _TOKEN.finditer(text):
        s = m.group()
        if m.lastgroup not in ("ws", "comment"):
            toks.append(Tok(m.lastgroup, s, m.start(), m.end(), line))
        line += s.count("\n")
    return toks


def _expr_end(toks, i, stops=(",", ")", ";", "}", "]")):
    """Index just past the expression starting at toks[i]."""
    depth, j = 0, i
    while j < len(toks):
        t = toks[j]
        if depth == 0 and t.text in stops:
            break
        if (depth == 0 and j > i and t.line > toks[j - 1].line
                and t.text not in _OPERATORS and toks[j - 1].text not in _OPERATORS):
            break  # a new statement on the next line
        if t.text in "([{":
            depth += 1
        elif t.text in ")]}":
            depth -= 1
        j += 1
    return j


def _unit_at(body, i):
    """`units . x` at body[i] -> x, else None."""
    if (i + 2 < len(body) and body[i].text == "units" and body[i + 1].text == "."
            and body[i + 2].kind == "ident"):
        return body[i + 2].text
    return None


def _literal(seg):
    """Is this token run an editable number?

    Returns dict(value, unit, start, end, suffix) or None. The text between
    start and end gets replaced by the new number followed by `suffix`.
    """
    if not seg:
        return None
    neg = seg[0].text == "-"
    body = seg[1:] if neg else seg
    if not body:
        return None
    # k_carb(500.0) style: only the number inside changes
    if (not neg and len(body) == 4 and body[0].text in _FUNCS and body[1].text == "("
            and body[2].kind == "number" and body[3].text == ")"):
        n = body[2]
        return {"value": float(n.text), "unit": _FUNCS[body[0].text],
                "start": n.start, "end": n.end, "suffix": ""}
    # factors joined by '*': numbers and at most one `units.x`, optional trailing `/ units.y`
    value, unit, div, nums = 1.0, "", "", []
    i, want_factor = 0, True
    while i < len(body):
        t = body[i]
        if want_factor:
            if t.kind == "number":
                value *= float(t.text)
                nums.append(t)
                i += 1
            elif _unit_at(body, i) and not unit:
                unit = _unit_at(body, i)
                i += 3
            else:
                return None
            want_factor = False
        elif t.text == "*":
            want_factor = True
            i += 1
        elif t.text == "/" and _unit_at(body, i + 1) and i + 4 == len(body):
            div = _unit_at(body, i + 1)
            i += 4
        else:
            return None
    if want_factor or not nums:
        return None
    value = -value if neg else value
    unit_text = unit + (f"/{div}" if div else "")
    if len(nums) == 1 and body[0] is nums[0]:
        # `6500 * units.rpm`: only the number (and sign) changes
        return {"value": value, "unit": unit_text, "start": seg[0].start, "end": nums[0].end,
                "suffix": ""}
    suffix = (f" * units.{unit}" if unit else "") + (f" / units.{div}" if div else "")
    return {"value": value, "unit": unit_text, "start": seg[0].start, "end": seg[-1].end,
            "suffix": suffix}


def _scaled_number(seg):
    """`50 * lift_scale` or `50` -> literal for just the number (flow samples)."""
    if seg and seg[0].kind == "number" and (
            len(seg) == 1 or (len(seg) == 3 and seg[1].text == "*" and seg[2].kind == "ident")):
        n = seg[0]
        return {"value": float(n.text), "unit": "", "start": n.start, "end": n.end, "suffix": ""}
    return None


def parse(text):
    """Return (items, name_item, imports).

    items: dicts with id, key, value, start, end, text, suffix, unit, context,
    node, default, line (+ gear / pair / label for some kinds).
    name_item: the engine name string or None. imports: [(path, start, end)].
    """
    toks = tokenize(text)
    items, imports = [], []
    calls, braces = [], []
    name_item = None
    gear_no = 0

    def add(key, lit, line, **extra):
        item = {"id": len(items), "key": key, "value": lit["value"], "start": lit["start"],
                "end": lit["end"], "text": text[lit["start"]:lit["end"]], "suffix": lit["suffix"],
                "unit": lit["unit"], "context": " > ".join(c for c in calls if c != "("),
                "node": next((b for b in reversed(braces) if b), ""), "default": False,
                "line": line}
        item.update(extra)
        items.append(item)
        return item

    k = 0
    while k < len(toks):
        t = toks[k]
        if t.text == "(":
            prev = toks[k - 1] if k else None
            if prev is not None and prev.kind == "ident":
                before = toks[k - 2] if k > 1 else None
                if before is not None and before.text == ".":
                    calls.append("." + prev.text)
                elif before is not None and before.kind == "ident" and before.text not in _KEYWORDS:
                    calls.append(f"{before.text} {prev.text}")
                else:
                    calls.append(prev.text)
            else:
                calls.append("(")
        elif t.text == ")":
            if calls:
                calls.pop()
        elif t.text == "{":
            braces.append(toks[k - 1].text if k > 1 and toks[k - 2].text == "node" else None)
        elif t.text == "}":
            if braces:
                braces.pop()
        elif t.text == "import" and k + 1 < len(toks) and toks[k + 1].kind == "string":
            s = toks[k + 1]
            imports.append((s.text[1:-1], s.start, s.end))
        elif t.text == ":" and k > 0:
            # `key: value` (named argument) or `input key [type]: default;`
            j = k - 1
            if toks[j].text == "]":
                while j > 0 and toks[j].text != "[":
                    j -= 1
                j -= 1
            key_tok = toks[j] if j >= 0 else None
            if key_tok is not None and key_tok.kind == "ident":
                seg = toks[k + 1:_expr_end(toks, k + 1)]
                if len(seg) == 1 and seg[0].kind == "string":
                    if key_tok.text == "name":
                        s = seg[0]
                        ctx = calls[-1] if calls else ""
                        is_engine = ctx.split(" ")[0] in ("engine", "wankel_engine")
                        if name_item is None or (is_engine and not name_item["engine"]):
                            name_item = {"value": s.text[1:-1], "start": s.start, "end": s.end,
                                         "engine": is_engine}
                else:
                    lit = _literal(seg)
                    if lit:
                        add(key_tok.text, lit, key_tok.line,
                            default=j > 0 and toks[j - 1].text == "input")
        elif (t.text == "label" and k + 2 < len(toks) and toks[k + 1].kind == "ident"
              and toks[k + 2].text == "("):
            lit = _literal(toks[k + 3:_expr_end(toks, k + 3)])
            if lit:
                add(toks[k + 1].text, lit, t.line, label=True)
        elif t.text == "." and k + 2 < len(toks) and toks[k + 2].text == "(":
            method = toks[k + 1].text
            if method in ("add_gear", "add_sample", "add_flow_sample"):
                a_end = _expr_end(toks, k + 3)
                a, b = toks[k + 3:a_end], []
                if a_end < len(toks) and toks[a_end].text == ",":
                    b = toks[a_end + 1:_expr_end(toks, a_end + 1)]
                if method == "add_gear":
                    lit = _literal(a)
                    if lit:
                        gear_no += 1
                        add("gear", lit, t.line, gear=gear_no)
                elif method == "add_sample":
                    la, lb = _literal(a), _literal(b)
                    if la and lb:
                        timing = la["unit"] == "rpm" and lb["unit"] == "deg"
                        x = add("timing_rpm" if timing else "sample_x", la, t.line)
                        add("timing_advance" if timing else "sample_y", lb, t.line, pair=x["value"])
                else:
                    la, lb = _scaled_number(a), _scaled_number(b)
                    if la and lb:
                        la["unit"], lb["unit"] = "thou", "cfm @28inH2O"
                        x = add("flow_lift", la, t.line)
                        add("flow", lb, t.line, pair=x["value"])
        k += 1
    return items, name_item, imports


# --------------------------------------------------------------------------
# Friendly "common settings" view
# --------------------------------------------------------------------------

def _last_call(context):
    return context.split(" > ")[-1] if context else ""


def _instance(context):
    return _last_call(context).split(" ")[-1]


def _innermost_type(context):
    return _last_call(context).split(" ")[0]


# key -> (group, label); label may use {inst} {n} {rpm}
_COMMON = {
    "redline": ("Rev limits", "Redline (tach / dyno)"),
    "rev_limit": ("Rev limits", "Rev limiter (ignition cut)"),
    "limiter_duration": ("Rev limits", "Limiter cut time"),
    "dyno_max_speed": ("Rev limits", "Dyno max speed"),
    "starter_torque": ("Starting & idle", "Starter torque"),
    "starter_speed": ("Starting & idle", "Starter speed"),
    "idle_throttle_plate_position": ("Starting & idle", "Idle throttle plate (nearer 1 = less idle air)"),
    "timing_advance": ("Ignition timing", "Advance at {rpm} rpm"),
    "audio_volume": ("Sound", "Exhaust volume ({inst})"),
    "hf_gain": ("Sound", "High-frequency gain"),
    "noise": ("Sound", "Noise"),
    "jitter": ("Sound", "Jitter"),
    "gear": ("Gearbox", "Gear {n} ratio"),
    "max_clutch_torque": ("Gearbox", "Clutch max torque"),
    "mass": ("Vehicle", "Vehicle mass"),
    "diff_ratio": ("Vehicle", "Final drive ratio"),
    "tire_radius": ("Vehicle", "Tire radius"),
    "drag_coefficient": ("Vehicle", "Drag coefficient"),
    "duration_at_50_thou": ("Cam", "{inst} duration @ 0.050\""),
    "lift": ("Cam", "{inst} lift"),
    "lobe_separation": ("Cam", "Lobe separation ({inst})"),
    "intake_lobe_center": ("Cam", "Intake lobe center ({inst})"),
    "exhaust_lobe_center": ("Cam", "Exhaust lobe center ({inst})"),
    "intake_flow_rate": ("Engine", "Throttle body flow ({inst})"),
    "chamber_volume": ("Engine", "Combustion chamber volume (compression)"),
    "friction_torque": ("Engine", "Crank friction"),
    "moment_of_inertia": ("Engine", "Crank + flywheel inertia ({inst})"),
    "simulation_frequency": ("Simulation", "Simulation frequency"),
}
GROUP_ORDER = ["Rev limits", "Starting & idle", "Ignition timing", "Sound", "Gearbox", "Vehicle",
               "Cam", "Engine", "Simulation"]
REV_KEYS = ("redline", "rev_limit", "dyno_max_speed")


def _common_ok(item):
    key, inner = item["key"], _innermost_type(item["context"])
    if key == "mass":
        return inner == "vehicle"
    if key in ("lift", "duration_at_50_thou"):
        return inner == "harmonic_cam_lobe"
    if key == "moment_of_inertia":
        return inner == "crankshaft"
    if key == "intake_flow_rate":
        return inner == "intake"
    return True


def effective(items):
    """Drop node defaults that a call site overrides (engine-sim uses the call site)."""
    call_site = {it["key"] for it in items if not it["default"]}
    return [it for it in items if not (it["default"] and it["key"] in call_site)]


def common_items(items):
    """[(group, label, item)] for the friendly view."""
    out = []
    chosen = effective([i for i in items if i["key"] in _COMMON and _common_ok(i)])
    if any(i["key"] in ("intake_lobe_center", "exhaust_lobe_center") and not i["default"]
           for i in chosen):
        # explicit lobe centers override the builder's lobe_separation default
        chosen = [i for i in chosen if not (i["key"] == "lobe_separation" and i["default"])]
    for it in chosen:
        group, label = _COMMON[it["key"]]
        label = label.format(inst=_instance(it["context"]) or it["node"] or "?",
                             n=it.get("gear", ""), rpm=f"{it.get('pair', 0):,.0f}")
        if it["default"]:
            label += " (node default)"
        out.append((group, label, it))
    out.sort(key=lambda r: (GROUP_ORDER.index(r[0]), r[2]["start"]))
    return out


def item_label(item):
    """Short name for the 'show every number' list."""
    key = item["key"]
    if key == "gear":
        text = f"gear {item['gear']} ratio"
    elif key == "timing_advance":
        text = f"timing advance @ {item['pair']:g} rpm"
    elif key == "timing_rpm":
        text = "timing sample (rpm)"
    elif key == "flow":
        text = f"port flow @ {item['pair']:g} thou lift"
    elif key == "flow_lift":
        text = "port flow sample (lift)"
    elif key in ("sample_x", "sample_y"):
        text = f"curve sample {key[-1]}"
    elif item.get("label"):
        text = f"label {key}"
    else:
        text = key
    return text + (" (default)" if item["default"] else "")


def describe(item):
    if item["default"]:
        return f"line {item['line']}: default in node {item['node']}"
    where = item["context"] or ("label" if item.get("label") else "")
    if item["node"]:
        where = f"{item['node']} > {where}" if where else item["node"]
    return f"line {item['line']}: {where}"


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------

def format_number(value, original, key):
    if key in _INT_KEYS:
        return str(int(round(value)))
    plain = original.lstrip("- ")
    if plain and plain[0].isdigit() and re.fullmatch(r"\d+", plain) and float(value).is_integer():
        return str(int(value))
    s = f"{value:.10f}".rstrip("0")
    if s.endswith("."):
        s += "0"
    return "0.0" if s == "-0.0" else s


def build_text(text, items, new_values, new_name=None, name_item=None, import_fix=None):
    """Text with edited numbers, engine name and import paths substituted.

    new_values: {item id: float}. import_fix: {(start, end): new path}.
    """
    repl = []
    by_id = {it["id"]: it for it in items}
    for iid, value in new_values.items():
        it = by_id[iid]
        if value != it["value"]:
            repl.append((it["start"], it["end"],
                         format_number(value, it["text"], it["key"]) + it["suffix"]))
    if new_name is not None and name_item is not None and new_name != name_item["value"]:
        safe = new_name.replace("\\", "/").replace('"', "'")
        repl.append((name_item["start"], name_item["end"], f'"{safe}"'))
    for (start, end), path in (import_fix or {}).items():
        repl.append((start, end, f'"{path}"'))
    # engine-sim can't read numbers like `.5`; give them a leading zero
    for t in tokenize(text):
        if t.kind == "number" and t.text.startswith(".") and not any(
                s <= t.start < e for s, e, _ in repl):
            repl.append((t.start, t.start, "0"))
    out = text
    for start, end, new in sorted(repl, key=lambda r: r[0], reverse=True):
        out = out[:start] + new + out[end:]
    return out


def import_fixes(imports, src_dir, dst_dir):
    """Relative imports that must be re-pointed when the file moves folders."""
    fixes = {}
    if os.path.normcase(os.path.abspath(src_dir)) == os.path.normcase(os.path.abspath(dst_dir)):
        return fixes
    for path, start, end in imports:
        target = os.path.join(src_dir, path)
        if os.path.isfile(target) and not os.path.isfile(os.path.join(dst_dir, path)):
            fixes[(start, end)] = os.path.relpath(target, dst_dir).replace("\\", "/")
    return fixes


def write_clone(src_path, dst_path, text, items, new_values, new_name, name_item, imports,
                engines_root):
    fixes = import_fixes(imports, os.path.dirname(src_path), os.path.dirname(dst_path))
    body = build_text(text, items, new_values, new_name, name_item, fixes)
    if body.startswith(CLONE_MARK):
        body = body.split("\n", 1)[1] if "\n" in body else ""
        origin = text.split("\n", 1)[0][len(CLONE_MARK):].split(" on ")[0].strip()
    else:
        origin = "from engines/" + os.path.relpath(src_path, engines_root).replace("\\", "/")
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    nl = "\r\n" if "\r\n" in text else "\n"
    with open(dst_path, "w", encoding="utf-8", newline="") as fh:
        fh.write(f"{CLONE_MARK} {origin} on {stamp}{nl}" + body)


def is_clone(text):
    return text.startswith(CLONE_MARK)


def list_engines(engines_root):
    """[(relative path, absolute path)] of .mr files that are runnable engines."""
    out = []
    for dirpath, _, files in os.walk(engines_root):
        for f in files:
            if not f.lower().endswith(".mr"):
                continue
            path = os.path.join(dirpath, f)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                continue
            if re.search(r"^\s*main\(\)", text, re.M) or "set_engine(" in text:
                out.append((os.path.relpath(path, engines_root).replace("\\", "/"), path))
    out.sort(key=lambda r: r[0].lower())
    return out
