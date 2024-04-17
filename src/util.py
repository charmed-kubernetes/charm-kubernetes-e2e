"""This module contains utility functions that are used by the charm."""

import subprocess


def determine_arch() -> str:
    """Dpkg wrapper to surface the architecture we are tied to."""
    cmd = ["dpkg", "--print-architecture"]
    output = subprocess.check_output(cmd).decode("utf-8")

    return output.rstrip()
