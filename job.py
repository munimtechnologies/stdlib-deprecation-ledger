"""Data run: scan Doc/library deprecation notes on CPython 3.9-3.15 and main, probe the
named objects in interpreters 3.8-3.15 (3.16 if available), grade PREREG.md, and write
the ledger (ledger.json / ledger.csv).

MV2, Munim, Inc. Apache-2.0. Made with AI agents.
"""
import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ledger  # noqa: E402

UA = {"User-Agent": "mv2-stdlib-deprecation-ledger/0.2 (Munim, Inc.; mv2@munimtech.com)"}
BRANCHES = ["3.9", "3.10", "3.11", "3.12", "3.13", "3.14", "3.15", "main"]
# Run 1 (2026-11-01) failed here: CPython replaces an end-of-life branch (3.9, 3.10) with a
# tag of the same name, so refs/heads/3.9 is a 404. Try the branch first, then the tag.
TARBALLS = ["https://codeload.github.com/python/cpython/tar.gz/refs/heads/%s",
            "https://codeload.github.com/python/cpython/tar.gz/refs/tags/%s"]
PYLINT = ["https://raw.githubusercontent.com/pylint-dev/pylint/main/pylint/checkers/stdlib.py",
          "https://raw.githubusercontent.com/pylint-dev/pylint/main/pylint/checkers/imports.py"]
MINORS = list(range(8, 17))   # 3.16 is optional (pre-release, if uv has one)
REQUIRED = list(range(8, 16))
SKIP_MODULES = {"antigravity", "this", "__main__", "idlelib.idle"}
# Gate: module present in 3.a and absent in 3.b (PEP 594 / imp removals).
CONTROLS = {"asyncore": (11, 12), "imp": (11, 12), "cgi": (12, 13), "telnetlib": (12, 13)}
ALWAYS = ("json", "dumps")
MIN_ROWS_PER_BRANCH = 10
UV_ENV = dict(os.environ, UV_PYTHON_PREFERENCE="only-managed",
              UV_PYTHON_INSTALL_DIR="/tmp/uv-python")


def fetch(url, dest=None, tries=3):
    err = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=600) as r:
                if dest is None:
                    return r.read()
                with open(dest + ".part", "wb") as f:
                    shutil.copyfileobj(r, f)
                os.replace(dest + ".part", dest)
                return dest
        except Exception as e:  # network hiccup: retry
            err = e
        time.sleep(5 * (k + 1))
    raise err


def tarball_urls(ref):
    return [t % ref for t in TARBALLS]


def fetch_ref(ref, dest):
    """Download a branch tarball, falling back to a tag of the same name. Returns the URL."""
    err = None
    for url in tarball_urls(ref):
        try:
            fetch(url, dest, tries=2)
            return url
        except Exception as e:
            err = e
            print("fetch failed: %s (%s)" % (url, e), flush=True)
    raise err


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_library(path):
    docs = {}
    with tarfile.open(path, "r:gz") as tf:
        for m in tf:
            parts = m.name.split("/", 1)
            if len(parts) != 2 or not m.isfile():
                continue
            rel = parts[1]
            if rel.startswith("Doc/library/") and rel.endswith(".rst"):
                docs[rel] = tf.extractfile(m).read().decode("utf-8", "replace")
        commit = tf.pax_headers.get("comment", "")
    return docs, commit


def interpreter(minor):
    v = "3.%d" % minor
    r = subprocess.run(["uv", "python", "install", v], env=UV_ENV,
                       capture_output=True, text=True, timeout=1200)
    if r.returncode != 0:
        return None, (r.stderr or r.stdout)[-400:]
    r = subprocess.run(["uv", "python", "find", v], env=UV_ENV,
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0 or not r.stdout.strip():
        return None, (r.stderr or r.stdout)[-400:]
    return r.stdout.strip().splitlines()[-1], ""


def probe(py, module, quals, tmp):
    tin, tout = os.path.join(tmp, "in.json"), os.path.join(tmp, "out.json")
    with open(tin, "w", encoding="utf-8") as f:
        json.dump({"module": module, "quals": quals}, f)
    try:
        subprocess.run([py, "-I", os.path.join(HERE, "probe.py"), tin, tout], cwd=tmp,
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=120)
        with open(tout, encoding="utf-8") as f:
            got = json.load(f)
        return got["results"], [got["version"], got["releaselevel"]]
    except Exception:
        return {q: "error" for q in quals}, None
    finally:
        for p in (tin, tout):
            if os.path.exists(p):
                os.remove(p)


def gate(status, interpreters, rows_per_branch):
    det, ok = {}, True
    for mod, (a, b) in CONTROLS.items():
        st = ledger.norm(status.get(ledger.pkey(mod, ""), {}))
        good = st.get(a) == "yes" and st.get(b) == "no"
        det["control %s present 3.%d, absent 3.%d" % (mod, a, b)] = good
        ok = ok and good
    st = status.get(ledger.pkey(*ALWAYS), {})
    good = all(st.get(k) == "yes" for k in REQUIRED)
    det["json.dumps present 3.8-3.15"] = good
    ok = ok and good
    good = all(interpreters.get("3.%d" % k, {}).get("installed") for k in REQUIRED)
    det["interpreters 3.8-3.15 installed"] = good
    ok = ok and good
    for b in BRANCHES:
        n = rows_per_branch.get(b, 0)
        good = n >= MIN_ROWS_PER_BRANCH
        det["branch %s deprecated-removed rows >= %d (got %d)" % (b, MIN_ROWS_PER_BRANCH, n)] = good
        ok = ok and good
    return ("HELD" if ok else "FAILED"), det


def pylint_check(rows, texts):
    """Exploratory: is each main-branch deprecated object named in pylint's tables?"""
    out = []
    seen = set()
    for r in rows:
        if r["branch"] != "main" or not ledger.attached(r) or r["scoped"]:
            continue
        if r["dep_minor"] is None or r["dep_minor"] < 12:
            continue
        key = ledger.pkey(r["module"], r["qual"])
        if key in seen:
            continue
        seen.add(key)
        full = r["module"] + ("." + r["qual"] if r["qual"] else "")
        short = (r["qual"] or r["module"]).split(".")[-1]
        if any('"%s"' % full in t for t in texts):
            hit = "full"
        elif any('"%s"' % short in t for t in texts):
            hit = "short_only"
        else:
            hit = "absent"
        out.append({"module": r["module"], "qual": r["qual"], "kind": r["kind"],
                    "dep": r["dep"], "rem": r["rem"], "file": r["file"], "line": r["line"],
                    "pylint": hit})
    return out


def write_csv(path, rows, cols):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([r.get(c, "") if not isinstance(r.get(c), (list, dict))
                        else json.dumps(r.get(c), sort_keys=True) for c in cols])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/data")
    ap.add_argument("--out-dir", default="/out")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    fetched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    rows, sources, rows_per_branch = [], {}, {}
    for b in BRANCHES:
        path = os.path.join(a.data_dir, "cpython-%s-%s.tar.gz" % (b, fetched_at[:10]))
        url = "cached"
        if not os.path.exists(path):
            url = fetch_ref(b, path)
        docs, commit = read_library(path)
        br = []
        for name in sorted(docs):
            br.extend(ledger.scan(docs[name], name, b))
        rows.extend(br)
        rows_per_branch[b] = sum(1 for r in br if r["directive"] == "deprecated-removed")
        sources[b] = {"commit": commit, "tarball_sha256": sha256_file(path), "url": url,
                      "rst_files": len(docs), "rows": len(br),
                      "deprecated_removed_rows": rows_per_branch[b]}
        print("branch %s: %s, commit %s, %d files, %d rows"
              % (b, url, commit[:12], len(docs), len(br)), flush=True)

    targets = {}
    for r in rows:
        if ledger.attached(r) and r["module"] not in SKIP_MODULES:
            targets.setdefault(r["module"], set()).add(r["qual"])
    for mod in CONTROLS:
        targets.setdefault(mod, set()).add("")
    targets.setdefault(ALWAYS[0], set()).add(ALWAYS[1])

    uv_version = subprocess.run(["uv", "--version"], capture_output=True,
                                text=True).stdout.strip()
    status, interpreters = {}, {}
    with tempfile.TemporaryDirectory() as tmp:
        for minor in MINORS:
            py, err = interpreter(minor)
            if not py:
                interpreters["3.%d" % minor] = {"installed": False, "error": err}
                print("3.%d not installed: %s" % (minor, err.strip()[-200:]), flush=True)
                continue
            ver, found = None, 0
            for mod in sorted(targets):
                quals = sorted(targets[mod])
                res, v = probe(py, mod, quals, tmp)
                ver = ver or v
                for q, s in res.items():
                    status.setdefault(ledger.pkey(mod, q), {})[minor] = s
                    found += s == "yes"
            interpreters["3.%d" % minor] = {"installed": True, "version": ver,
                                            "names_found": found}
            print("3.%d probed: %s, %d names found" % (minor, ver, found), flush=True)

    verdict, details = gate(status, interpreters, rows_per_branch)
    claims = ledger.build_claims(rows)
    idx = ledger.doc_index(rows)
    stale = ledger.live_stale(rows, status)
    res = ledger.grade(claims, status, idx, stale)
    res["P0_gate"] = {"verdict": verdict, "details": details}
    if verdict != "HELD":
        for k in ("P1", "P2", "P3"):
            res[k]["verdict"] = "NOT_TESTABLE (gate failed)"

    texts = []
    for u in PYLINT:
        try:
            texts.append(fetch(u).decode("utf-8", "replace"))
        except Exception as e:
            print("pylint fetch failed:", u, e)
    pyl = pylint_check(rows, texts) if len(texts) == len(PYLINT) else []
    res["exploratory_pylint"] = {
        "files": PYLINT, "fetched": len(texts), "checked": len(pyl),
        "full": sum(1 for p in pyl if p["pylint"] == "full"),
        "short_only": sum(1 for p in pyl if p["pylint"] == "short_only"),
        "absent": sum(1 for p in pyl if p["pylint"] == "absent")}
    res["counts"] = {"rows": len(rows),
                     "attached": sum(1 for r in rows if ledger.attached(r)),
                     "unattached": sum(1 for r in rows if not ledger.attached(r)),
                     "claims": len(claims), "modules_probed": len(targets),
                     "names_probed": sum(len(v) for v in targets.values())}
    res["source"] = {"fetched_at": fetched_at, "branches": sources, "uv": uv_version,
                     "interpreters": interpreters, "platform": sys.platform}

    # The ledger: one entry per documented deprecated object per branch, with presence.
    entries = {}
    for r in rows:
        if not ledger.attached(r):
            continue
        key = ledger.pkey(r["module"], r["qual"])
        e = entries.setdefault(key, {"module": r["module"], "qual": r["qual"],
                                     "kind": r["kind"], "notes": {}})
        e["notes"].setdefault(r["branch"], []).append(
            {"directive": r["directive"], "deprecated": r["dep"], "removed": r["rem"],
             "scoped": r["scoped"], "file": r["file"], "line": r["line"]})
    for key, e in entries.items():
        st = status.get(key, {})
        e["present"] = {"3.%d" % k: v for k, v in sorted(st.items())}
        lp = ledger.last_present(st)
        e["last_present"] = "3.%d" % lp if lp is not None else ""

    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    with open(os.path.join(a.out_dir, "ledger.json"), "w", encoding="utf-8") as f:
        json.dump({"source": res["source"], "entries": [entries[k] for k in sorted(entries)]},
                  f, indent=1, sort_keys=True)
    write_csv(os.path.join(a.out_dir, "rows.csv"), rows,
              ["branch", "file", "line", "directive", "kind", "module", "qual", "dep",
               "rem", "scoped", "text"])
    clist = sorted(claims.values(), key=lambda c: (c["module"], c["qual"], c["rem_minor"]))
    for c in clist:
        c["present"] = {"3.%d" % k: v for k, v in
                        sorted(status.get(ledger.pkey(c["module"], c["qual"]), {}).items())}
    ccols = ["module", "qual", "kind", "dep", "rem_minor", "branches", "scoped", "removal",
             "primary", "doc_state_in_z", "last_present", "file", "line", "present"]
    write_csv(os.path.join(a.out_dir, "claims.csv"), clist, ccols)
    write_csv(os.path.join(a.out_dir, "live_stale.csv"),
              [stale[k] for k in sorted(stale)],
              ["module", "qual", "rem_minor", "branches", "file", "line"])
    write_csv(os.path.join(a.out_dir, "pylint_check.csv"), pyl,
              ["module", "qual", "kind", "dep", "rem", "file", "line", "pylint"])

    print("P0", verdict, json.dumps(details))
    for k in ("P1", "P2", "P3"):
        print(k, json.dumps(res[k], sort_keys=True))
    for c in clist:
        if c["primary"] and c["removal"] != "on_time":
            print("CLAIM", c["module"], c["qual"], "3.%d" % c["rem_minor"], c["removal"],
                  c["doc_state_in_z"], c["file"], c["line"])
    for k in sorted(stale):
        s = stale[k]
        print("STALE", k, "3.%d" % s["rem_minor"], ",".join(s["branches"]), s["file"], s["line"])


if __name__ == "__main__":
    main()
