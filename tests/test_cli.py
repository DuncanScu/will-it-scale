import contextlib
import io
import os
import tempfile
import unittest
from unittest.mock import patch

from will_it_scale.__main__ import run_checks


class RunChecksTests(unittest.TestCase):
    def _run_in_tmp(self, **kwargs) -> str:
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            cwd = os.getcwd()
            os.chdir(directory)
            try:
                with contextlib.redirect_stdout(out):
                    run_checks(**kwargs)
            finally:
                os.chdir(cwd)
        return out.getvalue()

    def test_manifest_source_prints_and_saves(self) -> None:
        text = self._run_in_tmp(source="manifest", namespace=None, interpret=False)
        self.assertIn("Source: manifest", text)
        self.assertIn("Findings:", text)
        self.assertIn("Saved:", text)
        # The bundled fixture's known issues must surface.
        self.assertIn("order-service", text)

    def test_manifest_source_is_default_without_env(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            text = self._run_in_tmp(source=None, namespace=None, interpret=False)
        self.assertIn("Source: manifest", text)

    def test_interpret_flag_invokes_interpretation(self) -> None:
        # interpret=True must call the interpretation layer (mocked, no network).
        with patch("will_it_scale.interpret.interpret_findings", return_value={
            "executive_summary": "stub summary",
            "top_risks": [],
            "themes": [],
        }) as interpret:
            text = self._run_in_tmp(source="manifest", namespace=None, interpret=True)
        interpret.assert_called_once()
        self.assertIn("Foundry interpretation", text)


if __name__ == "__main__":
    unittest.main()
