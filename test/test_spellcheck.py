import subprocess
import tempfile
import os
import pytest
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "git-spell-check.py"

def run_script(args=[], input_text=None):
    cmd = ["python3", str(SCRIPT_PATH)] + args
    result = subprocess.run(cmd, input=input_text, capture_output=True, text=True)
    return result

def test_diff_string_input():
    example_diff = """
diff --git a/file.md b/file.md
index abc123..def456 100644
--- a/file.md
+++ b/file.md
@@ -1 +1,2 @@
 This is a sentence with a speling mistake.
+Another bad werd here.
"""
    result = run_script(["--input-string", example_diff])
    assert "speling" not in result.stdout
    assert "werd" in result.stdout
    assert "::error" in result.stdout  # GitHub annotation format

def test_file_input(tmp_path):
    file = Path(__file__).parent / "fixtures/example.diff"
    result = run_script(["--diff-file", file])
    assert "Thiss" in result.stdout
    assert "shold" not in result.stdout
    assert "Thisss" not in result.stdout

def test_empty_string():
    result = run_script(["--input-string", " "])
    assert result.returncode == 0
    assert result.stdout.strip() == "✅ No typos found."

def test_help_flag():
    result = run_script(["--help"])
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()
