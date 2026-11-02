"""Unit tests with hand-traced expectations. MV2, Munim, Inc. Apache-2.0. Made with AI agents."""
import unittest

import job
import ledger

FIX = """\
:mod:`!oldmod` --- Old module
=============================

.. module:: oldmod
   :synopsis: Old.

.. deprecated-removed:: 3.11 3.13
   The :mod:`!oldmod` module is deprecated.

--------------

.. function:: alpha(x)

   Does alpha.

   .. deprecated-removed:: 3.12 3.14
      Use :func:`beta` instead.

.. function:: gamma(x, flag=False)

   .. deprecated-removed:: 3.12 3.14
      Passing *flag* is deprecated.

.. class:: Box()

   .. method:: open()

      .. deprecated:: 3.13

.. note::

   .. deprecated-removed:: 3.10 3.12
      Stray.
"""

FIX2 = """\
.. currentmodule:: pkg.sub

.. data:: ONE
          TWO

   Constants.

   .. deprecated-removed:: 3.13 3.15
"""

PATH = "Doc/library/oldmod.rst"


def brief(rows):
    return [(r["kind"], r["module"], r["qual"], r["line"], r["directive"], r["dep_minor"],
             r["rem_minor"], r["scoped"]) for r in rows]


class TestScan(unittest.TestCase):
    def test_fixture(self):
        rows = ledger.scan(FIX, PATH, "3.13")
        self.assertEqual(brief(rows), [
            ("module", "oldmod", "", 7, "deprecated-removed", 11, 13, False),
            ("function", "oldmod", "alpha", 16, "deprecated-removed", 12, 14, False),
            ("function", "oldmod", "gamma", 21, "deprecated-removed", 12, 14, True),
            ("method", "oldmod", "Box.open", 28, "deprecated", 13, None, False),
            ("unattached", None, None, 32, "deprecated-removed", 10, 12, False),
        ])
        self.assertEqual(rows[0]["text"], "The :mod:`!oldmod` module is deprecated.")
        self.assertEqual(rows[1]["text"], "Use :func:`beta` instead.")
        self.assertEqual(rows[3]["text"], "")
        self.assertTrue(all(r["branch"] == "3.13" for r in rows))

    def test_multi_signature(self):
        rows = ledger.scan(FIX2, "f2", "3.15")
        self.assertEqual(brief(rows), [
            ("data", "pkg.sub", "ONE", 8, "deprecated-removed", 13, 15, False),
            ("data", "pkg.sub", "TWO", 8, "deprecated-removed", 13, 15, False),
        ])

    def test_scoped_regex(self):
        self.assertFalse(ledger.SCOPED.search("Use :func:`getlocale` instead of getdefaultlocale."))
        self.assertTrue(ledger.SCOPED.search("The *encoding* parameter"))
        self.assertTrue(ledger.SCOPED.search("Keyword arguments are deprecated."))


class TestStatus(unittest.TestCase):
    def test_removal_status(self):
        rs = ledger.removal_status
        self.assertEqual(rs(13, {12: "yes", 13: "no", 14: "no"}), "on_time")
        self.assertEqual(rs(14, {13: "yes", 14: "yes", 15: "no"}), "slipped")
        self.assertEqual(rs(14, {11: "yes", 12: "no", 13: "no_module", 14: "no"}), "early")
        self.assertEqual(rs(14, {13: "yes"}), "untested")
        self.assertEqual(rs(14, {13: "error", 14: "no"}), "import_error")
        self.assertEqual(rs(14, {13: "no", 14: "no"}), "never_found")
        self.assertEqual(rs(14, {12: "no", 13: "no", 14: "no", 15: "yes"}), "odd")

    def test_last_present(self):
        self.assertEqual(ledger.last_present({8: "yes", 9: "yes", 10: "no_module"}), 9)
        self.assertIsNone(ledger.last_present({}))

    def test_doc_state(self):
        ds = ledger.doc_state
        self.assertEqual(ds(14, None), "dropped")
        self.assertEqual(ds(14, {"rems": [14], "plain": False}), "stale")
        self.assertEqual(ds(14, {"rems": [16], "plain": False}), "postponed")
        self.assertEqual(ds(14, {"rems": [], "plain": True}), "unscheduled")
        self.assertEqual(ds(14, {"rems": [None], "plain": False}), "unscheduled")
        self.assertEqual(ds(14, {"rems": [], "plain": False}), "dropped")


def fixture_world():
    rows = (ledger.scan(FIX, PATH, "3.13") + ledger.scan(FIX, PATH, "3.14")
            + ledger.scan(FIX2, "f2", "3.15"))
    status = {
        "oldmod:": {12: "yes", 13: "no_module", 14: "no_module", 15: "no_module"},
        "oldmod:alpha": {13: "yes", 14: "yes", 15: "yes"},
        "oldmod:gamma": {13: "yes", 14: "yes"},
        "pkg.sub:ONE": {14: "yes", 15: "no"},
        "pkg.sub:TWO": {14: "yes", 15: "yes"},
    }
    return rows, status


class TestGrade(unittest.TestCase):
    def test_claims_and_grade(self):
        rows, status = fixture_world()
        claims = ledger.build_claims(rows)
        self.assertEqual(sorted(claims), [("oldmod", "", 13), ("oldmod", "alpha", 14),
                                          ("oldmod", "gamma", 14), ("pkg.sub", "ONE", 15),
                                          ("pkg.sub", "TWO", 15)])
        self.assertEqual(claims[("oldmod", "alpha", 14)]["branches"], ["3.13", "3.14"])
        self.assertTrue(claims[("oldmod", "gamma", 14)]["scoped"])
        idx = ledger.doc_index(rows)
        stale = ledger.live_stale(rows, status)
        self.assertEqual(sorted(stale), ["oldmod:alpha", "pkg.sub:TWO"])
        self.assertEqual(stale["oldmod:alpha"]["branches"], ["3.14"])
        self.assertEqual(stale["oldmod:alpha"]["line"], 16)
        self.assertEqual(stale["pkg.sub:TWO"]["branches"], ["3.15"])
        res = ledger.grade(claims, status, idx, stale)
        self.assertEqual(claims[("oldmod", "", 13)]["removal"], "on_time")
        self.assertEqual(claims[("oldmod", "alpha", 14)]["removal"], "slipped")
        self.assertEqual(claims[("oldmod", "alpha", 14)]["doc_state_in_z"], "stale")
        self.assertFalse(claims[("oldmod", "gamma", 14)]["primary"])
        self.assertEqual(claims[("pkg.sub", "TWO", 15)]["doc_state_in_z"], "stale")
        self.assertEqual(claims[("pkg.sub", "TWO", 15)]["last_present"], 15)
        self.assertEqual(res["P1"]["n"], 4)
        self.assertEqual(res["P1"]["kept"], 2)
        self.assertEqual(res["P1"]["on_time"], 2)
        self.assertEqual(res["P1"]["slipped"], 2)
        self.assertAlmostEqual(res["P1"]["share"], 0.5)
        self.assertEqual(res["P1"]["verdict"], "failed")
        self.assertEqual(res["P2"]["stale"], 2)
        self.assertEqual(res["P2"]["verdict"], "held")
        self.assertEqual(res["P2"]["doc_states"], {"stale": 2})
        self.assertEqual(res["P3"]["candidates"], 2)
        self.assertEqual(res["claim_categories"], {"on_time": 2, "slipped": 3})


class TestJobHelpers(unittest.TestCase):
    def test_pylint_check(self):
        rows = ledger.scan(FIX2, "f2", "main") + ledger.scan(FIX, PATH, "main")
        got = job.pylint_check(rows, ['X = {"pkg.sub.ONE"}', 'Y = {"TWO"}'])
        self.assertEqual([(g["module"], g["qual"], g["pylint"]) for g in got], [
            ("pkg.sub", "ONE", "full"), ("pkg.sub", "TWO", "short_only"),
            ("oldmod", "alpha", "absent"), ("oldmod", "Box.open", "absent")])

    def test_gate(self):
        status = {"asyncore:": {11: "yes", 12: "no_module"}, "imp:": {11: "yes", 12: "no_module"},
                  "cgi:": {12: "yes", 13: "no_module"}, "telnetlib:": {12: "yes", 13: "no"},
                  "json:dumps": {k: "yes" for k in range(8, 16)}}
        interp = {"3.%d" % k: {"installed": True} for k in range(8, 16)}
        per = {b: 10 for b in job.BRANCHES}
        self.assertEqual(job.gate(status, interp, per)[0], "HELD")
        per["3.9"] = 9
        self.assertEqual(job.gate(status, interp, per)[0], "FAILED")
        per["3.9"] = 10
        status["cgi:"][13] = "yes"
        self.assertEqual(job.gate(status, interp, per)[0], "FAILED")

    def test_tarball_urls(self):
        # Branch first, then the tag that replaces an end-of-life branch (run-1 failure).
        self.assertEqual(job.tarball_urls("3.9"), [
            "https://codeload.github.com/python/cpython/tar.gz/refs/heads/3.9",
            "https://codeload.github.com/python/cpython/tar.gz/refs/tags/3.9"])


if __name__ == "__main__":
    unittest.main()
