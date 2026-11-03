# Grading: are CPython's documented removal dates kept? (run 1)

MV2, Munim, Inc. (mv2@munimtech.com). Graded 2026-11-02 against `PREREG.md`. Made with AI
agents working in MV2's name. Every graded claim that was not on time was read in the rst
source by those agents, not by a human. Code Apache-2.0; text and data CC BY 4.0.

Data run: `stdlib-deprecation-ledger-v2`, 2026-11-02 04:50-04:55 UTC. Docs from 3.9 and 3.10
(now tags), 3.11-3.15 and main (commit ids and tarball sha256 in `results/run1-summary.json`).
Interpreters: python-build-standalone 3.8.20, 3.9.25, 3.10.22, 3.11.18, 3.12.16, 3.13.18,
3.14.10, 3.15.2 and 3.16.0 alpha (Linux x86-64, uv 0.13.6).

The scan found 1,618 deprecation notes in `Doc/library`. Of these, 1,481 attach to an object
and 137 do not. They yield 121 distinct removal claims (module, name, 3.Z): 47 on time,
51 slipped, 20 not yet due, 2 never found (`msilib`, `nis`: Windows-only and
optional-dependency modules absent from these builds) and 1 untested. Graded claims (not
scoped to a parameter, attached as the primary object): **70**.

## Verdicts

| | Prediction | Result | Verdict |
|---|---|---|---|
| P0 | gate (controls, interpreters, >= 10 rows per branch) | all true; 22-63 `deprecated-removed` rows per branch | **HELD** |
| P1 | >= 75% of graded removal claims kept | 45 of 70 (64.3%); 0 early, 25 slipped | **FAILED** |
| P2 | >= half of graded slipped claims stale in the 3.Z docs | 9 of 25 (36%); 6 postponed, 8 dropped, 2 unscheduled | **FAILED** |
| P3 | >= 3 real live-stale notes on docs.python.org 3.14 / 3.15 / dev | 2 candidates, 0 real | **FAILED** |

All three predictions failed as written. Hand review shows why P1 and P2 failed: most of the
"slipped" claims are cases where the note is not about the object it sits under. The runtime
checks (section below) confirm that reading for every artefact they covered; the
pre-registered numbers above are not changed by them.

## Hand review of the 25 graded slipped claims

**16 are attachment artefacts.** The note is about a usage, a method or a namespace, but
`ledger.scan` attached it to the enclosing object, so the probe checked the wrong thing:

| Claim (module.name, 3.Z) | What the note is really about | What happened to that (runtime check) |
|---|---|---|
| `argparse.ArgumentParser.add_mutually_exclusive_group`, 3.14 | nesting `add_argument_group` / `add_mutually_exclusive_group` inside a mutually exclusive group | nesting works on 3.13, raises `ValueError` on 3.14: **removed on time; note correct** |
| `ast.NodeVisitor`, 3.14 | `visit_Num`, `visit_Str`, `visit_Bytes`, `visit_NameConstant`, `visit_Ellipsis` "will not be called in Python 3.14+" | `visit_Num` is called on 3.13, not on 3.14: **removed on time; note correct** |
| `builtins.open`, 3.10 | the `'U'` mode | `'U'` works on 3.10, raises `ValueError` on 3.11: **slipped one release; the 3.10 docs say "removed in version 3.10" (stale)** |
| `collections.abc.Sequence`, `MutableSequence`, 3.14 (2) | `ByteString`, which shares the same `.. class::` directive (collections.abc.rst:283) | see `ByteString` below |
| `importlib.machinery.SourcelessFileLoader`, 3.15 | its `load_module` method; see the markup bug below | `load_module` present on `SourcelessFileLoader` and `SourceFileLoader` in 3.14, absent from both in 3.15 and 3.16a1: **removed on time** (exploratory check) |
| `typing.IO`, `TextIO`, `BinaryIO` (3.12 and 3.13; 6) | the `typing.io` namespace ("The typing.io namespace is deprecated and will be removed") | `typing.io` / `typing.re` import on 3.12, `ModuleNotFoundError` on 3.13: **removed in 3.13, as the 3.10+ docs say** (the 3.9 docs' "3.12" was superseded) |
| `typing.Match`, `Pattern` (3.12 and 3.13; 4) | the `typing.re` namespace | same as `typing.io` |

**9 are real slips of the object itself:**

| Claim | Interpreters | 3.Z docs | Reading |
|---|---|---|---|
| `gettext.ldngettext`, `gettext.bind_textdomain_codeset`, `NullTranslations.lngettext`, `NullTranslations.output_charset`, `NullTranslations.set_output_charset`, `GNUTranslations.lngettext` (6 claims) | present in 3.10.22, absent in 3.11.18 | **stale** | promised for 3.10, removed in 3.11. docs.python.org/3.10 (3.10.22) shows "Deprecated since version 3.8, removed in version 3.10." for all of them |
| `collections.abc.ByteString`, 3.14 | present through 3.16a | postponed | removal moved to a later release; docs updated |
| `typing.ByteString`, 3.14 | present through 3.16a | postponed | same |
| `locale.getdefaultlocale`, 3.15 | present through 3.16a | dropped | deprecation withdrawn (pylint PR #11252); note removed |

The 6 gettext rows are the only real stale notes among the graded claims. The runtime check
adds a seventh stale note outside the graded set: `open()`'s `'U'` mode (an artefact row, so
not counted in P2). docs.python.org/3.10/library/functions.html (read 2026-11-02) shows
"Deprecated since version 3.4, removed in version 3.10: The 'U' mode.", while the same page's
prose still says `'U'` "is permitted" and "no longer has any effect", which is what 3.10.22
does. All seven are live on docs.python.org/3.10. But 3.10 reached end of life
on 2026-10-01 and its branch is now a tag, so they cannot be fixed.

Exploratory, post hoc, not a verdict: if the 16 artefacts are set aside and the 45 on-time
claims are taken at face value (they were not hand-read), 45 of 54 removal promises were kept
(83%). The pre-registered numbers above stand.

## P3: the two live-stale candidates

Both are on docs.python.org/3.14, /3.15 and /dev, and both are correct notes misread by the
scanner:

- `argparse` (argparse.rst:2093): `deprecated-removed:: 3.11 3.14`, "Calling
  add_argument_group or add_mutually_exclusive_group on a mutually exclusive group now raises
  an exception." It is about nesting, not the method.
- `ast.NodeVisitor` (ast.rst:2452): `deprecated-removed:: 3.8 3.14` about the `visit_Num`
  family. It is about those methods, not the class.

So none of the 2 candidates is real, against a bar of 3. The runtime checks confirm both
notes are right (`argparse_nested_group`, `nodevisitor_visit_num`).

## Runtime checks (run 2026-11-02)

Job `doc-runtime-checks-v1`, 2026-11-02 07:28-07:31 UTC, python-build-standalone interpreters
3.10.22-3.16.0a1 (Linux x86-64, via uv 0.13.6). The code and the expected outcome of every
graded cell are in munimtechnologies/branch-version-notes-audit (`check.py`, `EXPECTED.md`),
fixed before the run. **All 18 graded cells in the job matched; 0 mismatches.** The checks for
this ledger:

| Check | Interpreters | Expected | Got | Held? |
|---|---|---|---|---|
| `gettext_l_functions` (4 names present?) | 3.10 / 3.11 | all True / all False | all True / all False | yes |
| `open_U_mode` | 3.10 / 3.11 | ok / ValueError | ok / ValueError | yes |
| `typing_io_re_namespaces` | 3.12 / 3.13 | ok / error | ok / ModuleNotFoundError | yes |
| `argparse_nested_group` | 3.13 / 3.14 | ok / error | ok / ValueError | yes |
| `nodevisitor_visit_num` (called?) | 3.13 / 3.14 | True / False | True / False | yes |
| `sourceless_load_module` (exploratory) | 3.14 / 3.15 / 3.16a1 | none fixed | present / absent / absent | - |

What this changes: nothing in the verdicts. It confirms that the gettext notes and the `'U'`
mode note in the 3.10 docs are stale by one release, that the two P3 candidates are correct
notes, and that the `typing.io` / `typing.re` and `load_module` removals happened when the
current docs say. Limits: one platform (Linux), latest micro release of each minor, one probe
per check.

## A markup bug found during review (not graded)

In the 3.12, 3.13 and 3.14 `Doc/library/importlib.rst`, the body of
`SourcelessFileLoader.load_module` is not indented under its `.. method::` directive. The
description and the `deprecated-removed:: 3.6 3.15` note sit at 3 spaces, level with the
directive. In `SourceFileLoader.load_module` they sit at 6 and 9 spaces. So in the
`SourcelessFileLoader` entry, the method has an empty body, and the deprecation is part of
the class body after it. The flattened text of docs.python.org/3.14 reads the same for both
classes. The difference is in the HTML nesting, which we did not inspect. Suggested fix
(3.14, a bugfix branch): indent those lines by three spaces. Low severity.

## Exploratory: pylint lead list

For main-branch unscoped notes deprecated in 3.12 or later: 26 checked against pylint's
`checkers/stdlib.py` and `imports.py` on main. 8 are present by full dotted name, 7 only by
bare name, and 11 are absent (`results/pylint_check.csv`). This is a list of leads for pylint,
not a judgement on it.

## Limits

- Attachment is the main weakness: a note inside an object directive is credited to that
  object even when its text names a method, mode or namespace. A run 2 should attach notes
  by the first literal or `:meth:` reference in the note body, and should keep namespace
  notes apart.
- Presence is not behaviour, except for the six behaviour probes above. One platform (Linux);
  latest micro release of each minor.
- AI agents did the hand labels from the rst text. No human has checked them.

## Files

`results/run1-summary.json`, `results/ledger.json` (every note with the object's presence in
3.8-3.16a), `results/claims.csv`, `results/rows.csv`, `results/live_stale.csv`,
`results/pylint_check.csv`, `results/runtime-checks.json`. Runtime check code:
munimtechnologies/branch-version-notes-audit (`check.py`, `EXPECTED.md`).
