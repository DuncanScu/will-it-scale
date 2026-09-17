import tempfile
import unittest
from pathlib import Path

from will_it_scale.tools.application_source import (
    read_application_source_file,
    read_source_file,
)


class ApplicationPerformanceInvestigatorTests(unittest.TestCase):
    def test_reads_python_file_within_source_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source_root = Path(directory)
            source_file = source_root / "service.py"
            source_file.write_text("def handle_request(): pass", encoding="utf-8")

            content = read_application_source_file(source_root, "service.py")

        self.assertEqual(content, "def handle_request(): pass")

    def test_rejects_files_outside_source_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "inside"):
                read_application_source_file(Path(directory), "../outside.py")

    def test_reads_allowed_yaml_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source_root = Path(directory)
            manifest_file = source_root / "deployment.yaml"
            manifest_file.write_text("kind: Deployment", encoding="utf-8")

            content = read_source_file(source_root, "deployment.yaml", frozenset({".yaml"}))

        self.assertEqual(content, "kind: Deployment")


if __name__ == "__main__":
    unittest.main()