"""Report which documented names exist in this interpreter (one module per process).

Usage: python -I probe.py IN.json OUT.json, where IN.json is
{"module": "pkg.mod", "quals": ["", "func", "Class.method", ...]} ("" = the module).
Plain syntax so it runs on 3.8 and later. MV2, Munim, Inc. Apache-2.0. Made with AI agents.
"""
import importlib
import json
import sys
import warnings


def lookup(mod, qual):
    if not qual:
        return "yes"
    obj = mod
    for part in qual.split("."):
        try:
            obj = getattr(obj, part)
        except AttributeError:
            return "no"
        except BaseException:
            return "error"
    return "yes"


def main():
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, encoding="utf-8") as f:
        job = json.load(f)
    warnings.simplefilter("ignore")
    name = job["module"]
    mod, mod_status = None, "yes"
    try:
        mod = importlib.import_module(name)
    except ModuleNotFoundError as e:
        missing = e.name or ""
        if missing == name or name.startswith(missing + "."):
            mod_status = "no_module"
        else:
            mod_status = "import_error"
    except BaseException:
        mod_status = "import_error"
    results = {}
    for qual in job["quals"]:
        results[qual] = lookup(mod, qual) if mod is not None else mod_status
    out = {"version": list(sys.version_info[:3]), "releaselevel": sys.version_info[3],
           "module": mod_status, "results": results}
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f)


if __name__ == "__main__":
    main()
