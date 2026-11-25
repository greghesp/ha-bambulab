"""Run Ruff, but only report problems on lines changed since a base ref.

Most of the existing code predates Ruff, so a whole-repo check would fail on
every PR and a whole-repo reformat would conflict with every open PR. Instead
this checks just the lines a PR adds or modifies:

- `ruff check` findings whose range touches a changed line
- `ruff format` hunks that overlap a changed line

Usage (from the repo root, with ruff on PATH):

    python scripts/lint_changed_lines.py [--fix] [BASE_REF]   # default: origin/main

Locally this compares the working tree (including uncommitted edits) against
the merge base with BASE_REF. `--fix` formats only the changed lines (via
`ruff format --range`); lint findings are listed for fixing by hand, because
`ruff check --fix` would also rewrite untouched lines elsewhere in the file.
"""

import json
import os
import re
import shutil
import subprocess
import sys

REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true"


def run(args, check=True):
    return subprocess.run(
        args, cwd=REPO_ROOT, capture_output=True, text=True, check=check
    )


def changed_lines(base_ref):
    """Return {path: set(line numbers)} for lines added/modified since base_ref."""
    merge_base = run(["git", "merge-base", base_ref, "HEAD"]).stdout.strip()
    # No second ref: diff against the working tree, so local uncommitted edits count too.
    diff = run(
        [
            "git",
            "diff",
            "-U0",
            "--no-color",
            "--no-ext-diff",
            "--diff-filter=AMR",
            merge_base,
            "--",
            "*.py",
        ]
    ).stdout

    changed, path = {}, None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = None if line == "+++ /dev/null" else line[len("+++ b/") :]
        elif path and (m := HUNK_RE.match(line)):
            start, count = int(m.group(3)), int(m.group(4) or 1)
            if count:  # count == 0 is a pure deletion - nothing new to lint
                changed.setdefault(path, set()).update(range(start, start + count))
    return changed


def touches(lines, start, end):
    return any(n in lines for n in range(start, end + 1))


def lint_findings(ruff, changed):
    result = run(
        [*ruff, "check", "--output-format=json", "--force-exclude", *changed],
        check=False,
    )
    if result.returncode not in (0, 1):
        sys.exit(f"ruff check failed:\n{result.stderr}")

    findings = []
    for d in json.loads(result.stdout or "[]"):
        path = os.path.relpath(d["filename"], REPO_ROOT)
        start, end = d["location"]["row"], d["end_location"]["row"]
        if touches(changed.get(path, ()), start, end):
            findings.append((path, start, end, f"ruff {d['code']}", d["message"]))
    return findings


def blocks(lines):
    """Collapse a set of line numbers into contiguous (start, end) ranges."""
    out = []
    for n in sorted(lines):
        if out and n == out[-1][1] + 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return out


def format_findings(ruff, changed, fix):
    # --range formats only the changed lines, so fixing a PR never reformats
    # the untouched rest of a file (which would bury the real change in noise).
    findings = []
    for path, lines in changed.items():
        for start, end in blocks(lines):
            mode = [] if fix else ["--diff"]
            result = run(
                [
                    *ruff,
                    "format",
                    *mode,
                    "--force-exclude",
                    # The end position is exclusive (line:1), so end on the
                    # line after the block to include all of its last line.
                    f"--range={start}-{end + 1}",
                    path,
                ],
                check=False,
            )
            if result.returncode not in (0, 1):
                sys.exit(f"ruff format failed on {path}:\n{result.stderr}")
            if not fix and result.returncode == 1:
                findings.append(
                    (
                        path,
                        start,
                        end,
                        "ruff format",
                        "Not formatted - run `python scripts/lint_changed_lines.py --fix`.",
                    )
                )
    return findings


def report(path, start, end, title, message):
    if IN_CI:
        print(
            f"::error file={path},line={start},endLine={end},title={title}::{message}"
        )
    else:
        print(f"{path}:{start}: [{title}] {message}")


def main():
    args = sys.argv[1:]
    fix = "--fix" in args
    args = [a for a in args if a != "--fix"]
    base_ref = args[0] if args else "origin/main"
    if not shutil.which("ruff"):
        sys.exit(
            "ruff not found on PATH - install the version pinned in pyproject.toml."
        )
    ruff = ["ruff"]

    changed = changed_lines(base_ref)
    if not changed:
        print(f"No changed Python lines since {base_ref}.")
        return 0

    # Format first so the lint pass sees the formatted lines. Formatting can
    # shift line numbers, so re-read the diff before linting.
    format_problems = format_findings(ruff, changed, fix)
    if fix:
        changed = changed_lines(base_ref)
    findings = format_problems + lint_findings(ruff, changed)
    for finding in sorted(findings):
        report(*finding)

    if findings:
        print(
            f"\n{len(findings)} problem(s) on changed lines in {len(changed)} file(s). "
            "`python scripts/lint_changed_lines.py --fix` formats changed lines; "
            "fix the lint findings above by hand."
        )
        return 1
    if fix:
        print(f"Formatted changed lines in {len(changed)} file(s) - review and commit.")
        return 0
    print(f"Ruff is clean on changed lines in {len(changed)} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
