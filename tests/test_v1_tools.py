from __future__ import annotations

import subprocess
from pathlib import Path

from forgecode.tools.base import ToolContext
from forgecode.tools.git import git_diff
from forgecode.tools.patch import apply_patch


def run_git(workspace: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    )


def test_apply_patch_modifies_file(tmp_path: Path) -> None:
    run_git(tmp_path, "init")
    target = tmp_path / "hello.py"
    target.write_text("return 1\n", encoding="utf-8")
    patch = """\
diff --git a/hello.py b/hello.py
--- a/hello.py
+++ b/hello.py
@@ -1 +1 @@
-return 1
+return 2
"""

    result = apply_patch({"patch": patch}, ToolContext(tmp_path))

    assert result["applied"] is True
    assert target.read_text(encoding="utf-8") == "return 2\n"


def test_git_diff_reports_unstaged_change(tmp_path: Path) -> None:
    target = tmp_path / "hello.py"
    target.write_text("return 1\n", encoding="utf-8")
    run_git(tmp_path, "init")
    run_git(tmp_path, "config", "user.name", "ForgeCode Test")
    run_git(tmp_path, "config", "user.email", "forgecode@example.com")
    run_git(tmp_path, "add", "hello.py")
    run_git(tmp_path, "commit", "-m", "initial")
    target.write_text("return 2\n", encoding="utf-8")

    result = git_diff({"path": "hello.py"}, ToolContext(tmp_path))

    assert result["has_changes"] is True
    assert "-return 1" in result["diff"]
    assert "+return 2" in result["diff"]
