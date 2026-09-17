# -*- coding: utf-8 -*-
"""Tests de versionado de plataforma (api/versioning.py)."""
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))


class TestVersioning(unittest.TestCase):

    def test_matriz_completa(self):
        from versioning import VERSION_MATRIX, version_blob
        for clave in ("ARHIAX_RE_VERSION", "DICTUS_ENGINE_VERSION",
                      "GIS_ADAPTER_VERSION", "TITULUX_VERSION", "RULESET_VERSION"):
            self.assertIn(clave, VERSION_MATRIX)
            self.assertTrue(VERSION_MATRIX[clave])
        blob = version_blob()
        self.assertIn("GIT_COMMIT_SHA", blob)
        self.assertEqual(blob["ARHIAX_RE_VERSION"], VERSION_MATRIX["ARHIAX_RE_VERSION"])

    def test_version_line_legible(self):
        from versioning import version_line
        linea = version_line()
        self.assertIn("ARHIAX RE v", linea)
        self.assertIn("dictus v", linea)
        self.assertIn("Titulux v", linea)

    def test_git_sha_no_lanza(self):
        from versioning import git_commit_sha
        sha = git_commit_sha()  # nunca lanza; cadena vacía si no hay .git
        self.assertIsInstance(sha, str)


if __name__ == "__main__":
    unittest.main()
