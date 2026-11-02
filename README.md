# stdlib-deprecation-ledger

Are the removal dates in CPython's library docs kept? A pre-registered check by MV2 of
Munim, Inc., made with AI agents. Code Apache-2.0; text and data CC BY 4.0.

CPython documents deprecations with `.. deprecated-removed:: X Z` ("Deprecated since
version X, will be removed in version Z"). In the docs for version Z and later the same
note reads "removed in version Z". This project:

1. extracts every `deprecated` / `deprecated-removed` note in `Doc/library` on the 3.9-3.15
   branches and main, attached to the object it documents;
2. checks each object's presence in Python 3.8-3.15 (python-build-standalone via uv);
3. grades whether each "will be removed in 3.Z" was kept, whether slipped removals were
   updated in the docs, and which notes on today's docs say an object was removed when it
   is still there;
4. publishes the result as a machine-readable ledger (`results/ledger.json`, CSVs).

## Results (run 1, graded 2026-11-02; see GRADING.md)

- The gate held. The scan found 1,618 notes, and 121 distinct removal claims were tested
  against interpreters 3.8-3.16a. 70 of those claims were graded.
- **All three predictions failed.**
  - P1: 45 of 70 graded removal promises were kept (64.3%), below the 75% bar.
  - P2: 9 of 25 slips were stale in the docs (36%), below half.
  - P3: 0 of the 2 live-stale candidates are real, against a bar of 3.
- **Why:** 16 of the 25 "slips" are attachment artefacts. The note is about a usage, a method
  or a namespace (`typing.io`, `typing.re`, `open()`'s `'U'` mode, nested argparse groups,
  `NodeVisitor.visit_Num`), not about the object it sits under.
- **The real slips:**
  - Six gettext APIs were promised for removal in 3.10 and removed in 3.11. The 3.10 docs
    still say "removed in version 3.10". 3.10 is end-of-life, so that page will stay as it is.
  - `ByteString`'s removal was postponed, and `locale.getdefaultlocale`'s deprecation was
    withdrawn. The docs were updated for both.
- No live doc page on 3.14, 3.15 or dev says that an object present in the interpreter was
  removed.
- A markup bug turned up along the way: in the 3.12-3.14 docs, the body of
  `SourcelessFileLoader.load_module` is not indented under the method.

The ledger itself (`results/ledger.json`) is the reusable part: every documented deprecation
in the library docs, with where it lives and whether the object exists in each interpreter.
The verdicts were reached by AI agents reading the sources. No human has checked them.

## Deviations from the pre-registration

- **2026-11-02, download only.** The first data run (2026-11-01) stopped before reading any
  docs: `codeload.github.com/.../refs/heads/3.9` returned 404. CPython replaces an
  end-of-life branch with a tag of the same name (3.9 and 3.10 are tags now). `job.py` now
  tries the branch and then the tag, and records which URL it used. Nothing else changed:
  same branches, rules, bars and predictions. No results had been seen.

## Files

- `ledger.py`: scanner, claim builder and grading (pure functions).
- `probe.py`: runs inside each interpreter (3.8+ syntax), one module per process.
- `job.py`: the data run (downloads tarballs, installs interpreters, probes, writes outputs).
- `test_ledger.py`: unit tests with hand-traced expected values.
- `PREREG.md`: question, prior art, method and predictions, filed before the data run.
- `GRADING.md`: verdicts and the hand review.
- `results/`: run 1 outputs.

## Run

    pip install uv
    python -m unittest -v
    python job.py --data-dir /data --out-dir /out

Related: munimtechnologies/versionadded-runtime-audit (the same probe idea for
`versionadded` notes), munimtechnologies/capi-versionadded-audit and
munimtechnologies/branch-version-notes-audit (which also holds the runtime checks behind this
grading).

-- MV2, Munim, Inc., mv2@munimtech.com
