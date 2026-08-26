"""Report translation keys that are missing or stale relative to en.json.

Non-blocking by design: prints GitHub Actions ::warning:: annotations, writes
a step-summary table, and writes a PR-comment body to
COMMENT_OUTPUT_PATH - but always exits 0. The intent is visibility for
reviewers/maintainers (and the PR submitter), not a merge gate - a PR that
only touches English strings shouldn't be blocked on translations catching
up.
"""
import glob
import json
import os
import sys

TRANSLATIONS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                 "custom_components", "bambu_lab", "translations")
)

# Marker so the workflow's comment step can find-and-update its own previous
# comment on later pushes, instead of piling up a new one each time.
COMMENT_MARKER = "<!-- translation-parity-check -->"
COMMENT_OUTPUT_PATH = os.environ.get("COMMENT_OUTPUT_PATH", "translation_parity_comment.md")


def flatten(d, prefix=""):
    """Flatten a nested translation dict to {"a.b.c": "value"}."""
    out = {}
    for key, value in d.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(flatten(value, path))
        else:
            out[path] = value
    return out


def build_markdown(summary_rows, any_drift):
    if not any_drift:
        return "## Translation parity\n\nAll locales match `en.json`. :white_check_mark:\n"

    lines = [
        "## Translation parity",
        "",
        "This is informational only and does not block merging.",
        "",
        "| Locale | Missing keys | Stale keys |",
        "| --- | --- | --- |",
    ]
    for filename, missing, extra in summary_rows:
        lines.append(f"| `{filename}` | {len(missing)} | {len(extra)} |")
    lines += [
        "",
        "Run `python3 scripts/auto_translate.py` to fill in missing keys "
        "(requires network access to Google Translate).",
    ]
    return "\n".join(lines) + "\n"


def main():
    en_path = os.path.join(TRANSLATIONS_DIR, "en.json")
    with open(en_path, encoding="utf-8") as f:
        en_keys = set(flatten(json.load(f)).keys())

    summary_rows = []
    any_drift = False

    for filepath in sorted(glob.glob(os.path.join(TRANSLATIONS_DIR, "*.json"))):
        filename = os.path.basename(filepath)
        if filename == "en.json":
            continue

        with open(filepath, encoding="utf-8") as f:
            other_keys = set(flatten(json.load(f)).keys())

        missing = sorted(en_keys - other_keys)  # in en.json, not in this locale
        extra = sorted(other_keys - en_keys)    # in this locale, not in en.json (stale)

        if not missing and not extra:
            continue

        any_drift = True
        summary_rows.append((filename, missing, extra))

        if missing:
            print(f"::warning file={os.path.relpath(filepath)}::"
                  f"{filename} is missing {len(missing)} key(s) present in en.json: "
                  f"{', '.join(missing[:5])}{', ...' if len(missing) > 5 else ''}")
        if extra:
            print(f"::warning file={os.path.relpath(filepath)}::"
                  f"{filename} has {len(extra)} stale key(s) no longer in en.json: "
                  f"{', '.join(extra[:5])}{', ...' if len(extra) > 5 else ''}")

    markdown = build_markdown(summary_rows, any_drift)

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as f:
            f.write(markdown)

    # Written every run (whether drift was found or not) so the workflow's
    # comment step can also use it to update a previous "drift found"
    # comment to a "resolved" state once a later push fixes it.
    with open(COMMENT_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(f"{COMMENT_MARKER}\n{markdown}")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"drift={'true' if any_drift else 'false'}\n")

    if not any_drift:
        print("All locales match en.json.")

    # Always succeed - this check is informational, not a merge gate.
    return 0


if __name__ == "__main__":
    sys.exit(main())
