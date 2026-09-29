from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.verify_dcube_image import read_hex

ROOT = Path(__file__).resolve().parents[1]


class DcubeTests(unittest.TestCase):
    def test_identity_and_payload(self):
        with tempfile.TemporaryDirectory(prefix="mixer-app-test-") as directory:
            executable = Path(directory) / "dcube_app_test"
            subprocess.run([
                "cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "tutorial/nRF52840"),
                str(ROOT / "tests/dcube_app_test.c"), "-o", str(executable),
            ], check=True)
            subprocess.run([str(executable)], check=True)

    def test_hex_valid_and_rejected_records(self):
        valid = ":0400000001020304F2\n:00000001FF\n"
        with tempfile.TemporaryDirectory(prefix="mixer-hex-test-") as directory:
            path = Path(directory) / "test.hex"
            path.write_text(valid)
            self.assertEqual(read_hex(path), {0: 1, 1: 2, 2: 3, 3: 4})
            for invalid in (
                valid.replace("F2", "F3"),  # checksum
                valid.splitlines()[0],       # truncated file, missing EOF
                valid.splitlines()[0] + "\n" + valid,  # overlapping data
                valid + valid,              # data after EOF
                ":00000001FF\n",             # empty image
            ):
                with self.subTest(invalid=invalid):
                    path.write_text(invalid)
                    with self.assertRaises(ValueError):
                        read_hex(path)


if __name__ == "__main__":
    unittest.main()
