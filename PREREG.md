# Pre-registration: are CPython's documented removal dates kept? (run 1)

By MV2, Munim, Inc. Filed 2026-11-01, before the data run. Made with AI agents working in
MV2's name. Code Apache-2.0; text and results CC BY 4.0.

## Question

CPython's library docs mark deprecations with two directives:

- `.. deprecated:: X` (deprecated, no removal date), and
- `.. deprecated-removed:: X Z`, rendered as "Deprecated since version X, will be removed in
  version Z". When the docs' own version is Z or later, the same directive renders as
  "Deprecated since version X, **removed in version Z**" (`Doc/tools/extensions/changes.py`,
  `DeprecatedRemoved`: `current_version < removed_version` picks the "will be removed" label,
  otherwise the "removed in" label).

So a `deprecated-removed:: X 3.Z` note on an object that still exists in 3.Z tells readers
of the 3.Z docs that the object was removed when it was not. This run asks:

1. How often is "will be removed in 3.Z" kept, measured on the interpreters?
2. When a removal slips, do the 3.Z docs get updated?
3. How many such notes are live today on docs.python.org (3.14, 3.15, dev)?

It also publishes the **ledger**: every documented deprecation in Doc/library on 3.9-3.15
and main, with the object's observed presence in each interpreter 3.8-3.15. That is
machine-readable data about stdlib deprecations, checked against runtime. CPython does not
publish this today (gh-134222 has been open since May 2025 with no PR). pylint's maintainers
built their 3.15 list by hand (pylint PR #11252, August 2026) and asked for one on
discuss.python.org (thread 92039, 2026-08-12).

## Prior art (searched 2026-11-01)

- gh-134222 / discuss.python.org thread 92039: proposal for a machine-readable
  deprecation file (TOML -> JSON); C.A.M. Gerlach's 2023 prototype branch extended the
  `deprecated-removed` directive to emit CSV/JSON. Nothing merged; no runtime check.
- gh-154757 (July 2026): by hand, 26 C API items scheduled for removal in 3.16 still in
  `Include/`. C API only, one version, no tool.
- stdlib-radar (third-party): 83 hand-curated rules for APIs removed or changed in
  3.13-3.15, runtime-tested in CI. Covers removals only, three versions, not extracted
  from the docs, does not check the docs' promises.
- pylint `checkers/stdlib.py` / `imports.py`: hand-kept deprecation tables.
- CPython's `warnings._deprecated(..., remove=(3, Z))` fails at runtime once 3.Z is reached,
  so code that uses it cannot slip silently, but many deprecations do not use it, and
  it checks code, not docs.
- Ours: munimtechnologies/versionadded-runtime-audit (versionadded notes vs interpreters).

No tool or study was found that extracts every `deprecated-removed` note from the docs
on several branches and checks each removal promise against the interpreters.

## Data and method

- Docs: `Doc/library/**.rst` from the GitHub tarballs of branches 3.9, 3.10, 3.11, 3.12,
  3.13, 3.14, 3.15 and main, fetched at run time (commit ids and sha256 recorded).
- `ledger.scan` finds each `deprecated` / `deprecated-removed` directive and attaches it to
  the object directive it sits directly inside (module-level notes before the first rule
  line attach to the module). Anything else is "unattached" and not graded.
- A note is **scoped** if its text matches `param*`, `argument(s)`, `keyword*`, `passing`
  or an italic `*name*` (a parameter or calling form is deprecated, not the object).
  Scoped notes are listed but not graded.
- Interpreters: python-build-standalone 3.8-3.15 via `uv python install` (Linux x86-64);
  3.16 is tried and used only if uv has it. `probe.py` imports each module in a fresh
  `-I` process and walks `getattr` for each name.
- A **claim** is a distinct (module, name, 3.Z) from any branch. For Z in 3.9-3.15:
  `on_time` (present 3.(Z-1), absent 3.Z), `early` (absent in both, present earlier),
  `slipped` (present in 3.Z), plus untested/import_error/never_found/odd (not graded).
- For a slipped claim, the 3.Z branch docs are read for the same object: `stale` (still
  gives a removal version <= Z), `postponed` (only later versions), `unscheduled` (plain
  deprecated), `dropped` (no note left).
- **Live stale**: an unscoped attached note on 3.14, 3.15 or main whose removal version
  R <= min(branch, 3.15) while the object is present in interpreter min(branch, 3.15).

## Predictions (written before any data was fetched)

- **P0 (gate).** asyncore and imp import in 3.11 and not 3.12; cgi and telnetlib import in
  3.12 and not 3.13; json.dumps exists in 3.8-3.15; all of 3.8-3.15 install; every branch
  yields at least 10 `deprecated-removed` rows. If the gate fails, P1-P3 are NOT TESTABLE.
- **P1.** Of graded (unscoped, on_time/early/slipped) removal claims, at least **75%** are
  kept (object absent in 3.Z).
- **P2.** Of graded slipped claims, at least **half** are `stale` in the 3.Z branch docs.
- **P3.** Hand review of the live-stale candidates finds at least **3** real cases: notes
  on docs.python.org (3.14, 3.15 or dev) that give a reached removal version for an
  object that is still there, and that are not explained by a parameter/behaviour scope,
  a different object of the same name, or a parser artefact.

Exploratory (no prediction): for main-branch unscoped notes deprecated in 3.12 or later,
whether the dotted name (or the bare name) appears quoted in pylint's `stdlib.py` /
`imports.py` on main. That is a lead list for pylint, not a verdict on pylint.

## How blind this is

- No deprecation note was listed or counted before this file was written.
- Known in advance from reading: `platform.java_ver` (3.13 -> 3.15) was removed on time;
  `locale.getdefaultlocale` was postponed from 3.13 to 3.15 and its deprecation was later
  reversed (pylint PR #11252); gh-154757 shows the C API slips. These shaped the bars
  only loosely: P1's 75% and P2's 50% are judgement calls, close to coin flips.
- Known limits: presence is not the same as behaviour (a deprecated alias could stay
  as a stub that raises); instance attributes are not visible through the class; one
  platform (Linux); 3.Z means the latest 3.Z micro release uv installs.

Grading: GRADING.md after the run, with every graded non-on-time claim read by hand.
