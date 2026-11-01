"""Find every ``.. deprecated::`` and ``.. deprecated-removed::`` note in CPython's
Doc/library (any branch), name the object it is attached to, and grade each removal
promise ("deprecated since X, will be removed in 3.Z") against which interpreters
actually still have the object.

MV2, Munim, Inc. Apache-2.0. Made with AI agents.
"""
import re

OBJ_KINDS = ("function", "class", "method", "attribute", "data", "exception",
             "classmethod", "staticmethod", "property", "decorator",
             "decoratormethod", "coroutinefunction", "coroutinemethod",
             "abstractmethod")
CLASSLIKE = ("class", "exception")
DEPRECATION = ("deprecated", "deprecated-removed")
DIRECTIVE = re.compile(r"^( *)\.\. (?:py:)?([a-z][a-z-]*)::(.*)$")
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
VERSION = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?$")
RULE = re.compile(r"^([-=~^\"*+#])\1{3,}\s*$")
# Text that says the note is about a parameter or calling form, not the object itself.
SCOPED = re.compile(r"\b(param\w*|arguments?|keyword\w*|passing)\b|\*\w+\*", re.I)
FIRST_TESTABLE, LAST_TESTABLE = 9, 15   # removal 3.Z needs interpreters 3.(Z-1) and 3.Z
LIVE = {"3.14": 14, "3.15": 15, "main": 16}
P1_BAR = 0.75
P2_BAR = 0.5
P3_BAR = 3


def indent(line):
    return len(line) - len(line.lstrip(" "))


def first_name(sig):
    m = NAME.match(sig.strip())
    return m.group(0).rstrip(".") if m else None


def qualify(name, parent):
    if parent is None or parent["kind"] not in CLASSLIKE or not parent["qual"]:
        return name
    pq = parent["qual"]
    if name.split(".")[0] == pq.split(".")[-1]:  # written as Class.member already
        return pq.rsplit(".", 1)[0] + "." + name if "." in pq else name
    return pq + "." + name


def parse_version(tok):
    m = VERSION.match(tok or "")
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def body_text(lines, i, ind):
    """Text of the directive's content block (lines indented deeper than the directive)."""
    out = []
    for line in lines[i + 1:]:
        if line.strip() and indent(line) <= ind:
            break
        if line.strip():
            out.append(line.strip())
    return " ".join(out)


def scan(text, path="", branch=""):
    """One row per deprecated / deprecated-removed directive in an .rst file.

    kind is the marked object's directive, "module" for a module-level note before the
    file's first rule line or object, or "unattached" otherwise.
    """
    rows = []
    lines = text.splitlines()
    module = "builtins"
    fresh = False
    stack = []
    sig = None
    for i, line in enumerate(lines):
        if not line.strip():
            sig = None
            continue
        ind = indent(line)
        if sig is not None and ind > sig["indent"]:
            s = line.strip()
            if sig["cont"]:
                sig["cont"] = s.endswith("\\")
            elif not s.startswith(":"):
                n = first_name(s)
                if n:
                    sig["quals"].append(qualify(n, sig["parent"]))
                sig["cont"] = s.endswith("\\")
            continue
        sig = None
        while stack and stack[-1]["indent"] >= ind:
            stack.pop()
        if stack and stack[-1]["body"] is None:
            stack[-1]["body"] = ind
        if RULE.match(line):
            fresh = False
            continue
        m = DIRECTIVE.match(line)
        if not m:
            continue
        kind, arg = m.group(2), m.group(3).strip()
        if kind in ("module", "currentmodule"):
            module = None if arg == "None" else arg
            fresh = kind == "module"
        elif kind in OBJ_KINDS:
            fresh = False
            parent = stack[-1] if stack else None
            name = first_name(arg)
            qual = qualify(name, parent) if name else None
            entry = {"indent": ind, "kind": kind, "qual": qual,
                     "quals": [qual] if qual else [], "body": None,
                     "module": module, "parent": parent,
                     "cont": arg.endswith("\\")}
            stack.append(entry)
            sig = entry
        elif kind in DEPRECATION:
            tok = arg.split()
            dep = tok[0] if tok else ""
            if kind == "deprecated-removed":
                rem = tok[1] if len(tok) > 1 else ""
                tail = tok[2:]
            else:
                rem = ""
                tail = tok[1:]
            note = (" ".join(tail) + " " + body_text(lines, i, ind)).strip()
            dmaj, dmin = parse_version(dep)
            rmaj, rmin = parse_version(rem)
            base = {"branch": branch, "file": path, "line": i + 1, "directive": kind,
                    "dep": dep, "rem": rem,
                    "dep_minor": dmin if dmaj == 3 else None,
                    "rem_minor": rmin if rmaj == 3 else None,
                    "scoped": bool(SCOPED.search(note)), "text": note[:300]}
            if stack and stack[-1]["body"] == ind:
                owner = stack[-1]
                for q in owner["quals"]:
                    rows.append(dict(base, kind=owner["kind"], module=owner["module"],
                                     qual=q))
            elif not stack and ind == 0 and fresh and module:
                rows.append(dict(base, kind="module", module=module, qual=""))
            else:
                rows.append(dict(base, kind="unattached", module=None, qual=None))
    return rows


def attached(row):
    return row["kind"] != "unattached" and row["module"] is not None


def pkey(module, qual):
    return "%s:%s" % (module, qual)


def norm(st):
    return {k: ("no" if v == "no_module" else v) for k, v in st.items()}


def removal_status(z, st):
    """Was 'will be removed in 3.z' kept? st maps interpreter minor -> probe status."""
    if z not in st or (z - 1) not in st:
        return "untested"
    n = norm(st)
    cur, prev = n[z], n[z - 1]
    if cur not in ("yes", "no") or prev not in ("yes", "no"):
        return "import_error"
    if not any(v == "yes" for v in n.values()):
        return "never_found"
    if cur == "yes":
        return "slipped"
    if prev == "yes":
        return "on_time"
    if any(v == "yes" for k, v in n.items() if k < z - 1):
        return "early"
    return "odd"


def last_present(st):
    yes = [k for k, v in norm(st).items() if v == "yes"]
    return max(yes) if yes else None


def build_claims(rows):
    """Distinct removal promises (module, qual, 3.Z) found in any scanned branch."""
    claims = {}
    for r in rows:
        if r["directive"] != "deprecated-removed" or not attached(r) or r["rem_minor"] is None:
            continue
        key = (r["module"], r["qual"], r["rem_minor"])
        c = claims.setdefault(key, {"module": r["module"], "qual": r["qual"],
                                    "kind": r["kind"], "rem_minor": r["rem_minor"],
                                    "dep": r["dep"], "branches": [], "scoped": False,
                                    "file": r["file"], "line": r["line"]})
        if r["branch"] not in c["branches"]:
            c["branches"].append(r["branch"])
        c["scoped"] = c["scoped"] or r["scoped"]
    return claims


def doc_index(rows):
    idx = {}
    for r in rows:
        if not attached(r):
            continue
        e = idx.setdefault((r["branch"], r["module"], r["qual"]), {"rems": [], "plain": False})
        if r["directive"] == "deprecated-removed":
            e["rems"].append(r["rem_minor"])
        else:
            e["plain"] = True
    return idx


def doc_state(z, entry):
    """What the 3.z branch docs say about an object whose 3.z removal slipped."""
    if entry is None:
        return "dropped"
    rems = [x for x in entry["rems"] if x is not None]
    if any(x <= z for x in rems):
        return "stale"
    if any(x > z for x in rems):
        return "postponed"
    if entry["plain"] or entry["rems"]:
        return "unscheduled"
    return "dropped"


def live_stale(rows, status):
    """Objects whose notes on a maintained branch (3.14, 3.15, main) give a removal
    version the object has reached, while that interpreter still has it."""
    out = {}
    for r in rows:
        v = LIVE.get(r["branch"])
        if (v is None or r["directive"] != "deprecated-removed" or not attached(r)
                or r["rem_minor"] is None or r["scoped"]):
            continue
        at = min(v, LAST_TESTABLE)
        if r["rem_minor"] > at:
            continue
        st = norm(status.get(pkey(r["module"], r["qual"]), {}))
        if st.get(at) != "yes":
            continue
        key = pkey(r["module"], r["qual"])
        e = out.setdefault(key, {"module": r["module"], "qual": r["qual"],
                                 "rem_minor": r["rem_minor"], "branches": [],
                                 "file": r["file"], "line": r["line"]})
        if r["branch"] not in e["branches"]:
            e["branches"].append(r["branch"])
    return out


def grade(claims, status, idx, stale):
    """Mechanical verdicts for P1 and P2, and the P3 candidate count."""
    prim = []
    for c in claims.values():
        z = c["rem_minor"]
        st = status.get(pkey(c["module"], c["qual"]), {})
        if FIRST_TESTABLE <= z <= LAST_TESTABLE:
            c["removal"] = removal_status(z, st)
        else:
            c["removal"] = "not_due" if z > LAST_TESTABLE else "untested"
        c["last_present"] = last_present(st)
        c["doc_state_in_z"] = ""
        if c["removal"] == "slipped":
            c["doc_state_in_z"] = doc_state(z, idx.get(("3.%d" % z, c["module"], c["qual"])))
        c["primary"] = (not c["scoped"]) and c["removal"] in ("on_time", "early", "slipped")
        if c["primary"]:
            prim.append(c)
    kept = sum(1 for c in prim if c["removal"] in ("on_time", "early"))
    on_time = sum(1 for c in prim if c["removal"] == "on_time")
    slipped = [c for c in prim if c["removal"] == "slipped"]
    stale_n = sum(1 for c in slipped if c["doc_state_in_z"] == "stale")
    n = len(prim)
    share = kept / n if n else None
    s_share = stale_n / len(slipped) if slipped else None
    cats, states = {}, {}
    for c in claims.values():
        cats[c["removal"]] = cats.get(c["removal"], 0) + 1
    for c in slipped:
        states[c["doc_state_in_z"]] = states.get(c["doc_state_in_z"], 0) + 1
    return {
        "P1": {"n": n, "kept": kept, "on_time": on_time, "early": kept - on_time,
               "slipped": len(slipped), "share": share, "bar": P1_BAR,
               "verdict": "held" if share is not None and share >= P1_BAR else "failed"},
        "P2": {"slipped": len(slipped), "stale": stale_n, "share": s_share, "bar": P2_BAR,
               "doc_states": states,
               "verdict": "held" if s_share is not None and s_share >= P2_BAR else "failed"},
        "P3": {"candidates": len(stale), "bar": P3_BAR, "verdict": "pending hand review"},
        "claim_categories": cats,
    }
