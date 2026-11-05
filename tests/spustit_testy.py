"""Run the Dvojpanel GUI test suite on a fresh copy of the program.

    python tests\\spustit_testy.py

Needs Windows with a display and the Windchill project next to Dvojpanel (or DP_WINDCHILL); it is only
read. The program is copied into a temporary folder, so the local nastroje.json, oblibene.json and
dvojpanel.json are never touched. Takes about 5 minutes (a 300 MB copy test, window launches).
Exit code 0 = all checks passed.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
FILES = ["dvojpanel.py", "dvojpanel.ico", "nastroje.example.json", "README.md", "CHANGELOG.md"]


def main():
    with tempfile.TemporaryDirectory(prefix="dvojpanel_test_", ignore_cleanup_errors=True) as tmp:
        program = Path(tmp) / "Dvojpanel"
        (program / "nastroje").mkdir(parents=True)
        for name in FILES:
            shutil.copy2(REPO / name, program / name)
        shutil.copy2(REPO / "nastroje" / "ukazka.py", program / "nastroje" / "ukazka.py")
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        return subprocess.call([sys.executable, str(HERE / "harness.py"), str(program), str(Path(tmp) / "env")],
                               env=env)


if __name__ == "__main__":
    sys.exit(main())
