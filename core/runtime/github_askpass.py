"""Minimal non-persistent Git credential helper used by FRIDAY clone operations."""
from __future__ import annotations

import os
import sys


prompt = " ".join(sys.argv[1:]).lower()
token = os.environ.get("FRIDAY_GITHUB_TOKEN", "")

if "username" in prompt or "user" in prompt:
    sys.stdout.write("x-access-token\n")
elif "password" in prompt or "pass" in prompt:
    sys.stdout.write(token + "\n")
