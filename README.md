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

Status: pre-registered (see PREREG.md). Results and grading will follow in this repo.

## Files

- `ledger.py`: scanner, claim builder and grading (pure functions).
- `probe.py`: runs inside each interpreter (3.8+ syntax), one module per process.
- `job.py`: the data run (downloads tarballs, installs interpreters, probes, writes outputs).
- `test_ledger.py`: unit tests with hand-traced expected values.
- `PREREG.md`: question, prior art, method and predictions, filed before the data run.

## Run

    pip install uv
    python -m unittest -v
    python job.py --data-dir /data --out-dir /out

Related: munimtechnologies/versionadded-runtime-audit (the same probe idea for
`versionadded` notes) and munimtechnologies/capi-versionadded-audit.

-- MV2, Munim, Inc., mv2@munimtech.com
