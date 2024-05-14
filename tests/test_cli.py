import subprocess
import sys

from thorlabs_mff_fastcs import __version__


def test_cli_version():
    cmd = [sys.executable, "-m", "thorlabs_mff_fastcs", "--version"]
    assert subprocess.check_output(cmd).decode().strip() == __version__
