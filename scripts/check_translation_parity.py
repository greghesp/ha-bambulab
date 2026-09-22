"""Check translation keys and placeholders against en.json without editing them.

Translation findings, including missing/stale keys and placeholder errors, are
informational warnings and do not block merging. Reports are deterministic and
overwritten on each run. Source translations are never modified.
"""
import glob
import json
import os
import sys
from string import Formatter

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


def placeholder_names(text):
    """Respect escaped braces and placeholders in nested format specs."""
    names = set()
    for _, field, format_spec, _ in Formatter().parse(text):
        if field is not None:
            names.add(field)
            names.update(placeholder_names(format_spec))
    return names


def placeholder_errors(english, translated):
    """Compare flattened strings; include missing placeholder-bearing keys."""
    errors = {}
    for key, value in sorted(english.items()):
        if not isinstance(value, str):
            continue
        try:
            expected = placeholder_names(value)
        except ValueError as error:
            errors[key] = f"invalid English format string: {error}"
            continue
        if key not in translated:
            if expected:
                errors[key] = f"missing translation with placeholders {sorted(expected)}"
            continue
        if not isinstance(translated[key], str):
            errors[key] = "translation must be a string"
            continue
        try:
            actual = placeholder_names(translated[key])
        except ValueError as error:
            errors[key] = f"invalid translated format string: {error}"
            continue
        if actual != expected:
            errors[key] = f"expected {sorted(expected)}, got {sorted(actual)}"
    return errors


def build_markdown(summary_rows, any_drift):
    if not any_drift:
        return "## Translation parity\n\nAll locales match `en.json`. :white_check_mark:\n"

    lines = [
        "## Translation parity",
        "",
        "Missing/stale keys and placeholder errors are informational and do not block merging.",
        "",
        "| Locale | Missing keys | Stale keys | Placeholder errors |",
        "| --- | --- | --- | --- |",
    ]
    for filename, missing, extra, errors in summary_rows:
        lines.append(f"| `{filename}` | {len(missing)} | {len(extra)} | {len(errors)} |")
    for filename, _, _, errors in summary_rows:
        for key, message in errors.items():
            lines.append(f"\n- `{filename}:{key}`: {message}")
    lines += [
        "",
        "Run `python3 scripts/auto_translate.py` to fill in missing keys "
        "(requires network access to Google Translate). Preserve placeholder names "
        "exactly as in English and rerun this check afterwards.",
    ]
    return "\n".join(lines) + "\n"


def main():
    en_path = os.path.join(TRANSLATIONS_DIR, "en.json")
    with open(en_path, encoding="utf-8") as f:
        english = flatten(json.load(f))
    en_keys = set(english)

    summary_rows = []
    any_drift = False

    for filepath in sorted(glob.glob(os.path.join(TRANSLATIONS_DIR, "*.json"))):
        filename = os.path.basename(filepath)
        if filename == "en.json":
            continue

        with open(filepath, encoding="utf-8") as f:
            translated = flatten(json.load(f))
        other_keys = set(translated)

        missing = sorted(en_keys - other_keys)  # in en.json, not in this locale
        extra = sorted(other_keys - en_keys)    # in this locale, not in en.json (stale)
        errors = placeholder_errors(english, translated)

        if not missing and not extra and not errors:
            continue

        any_drift = True
        summary_rows.append((filename, missing, extra, errors))

        if missing:
            print(f"::warning file={os.path.relpath(filepath)}::"
                  f"{filename} is missing {len(missing)} key(s) present in en.json: "
                  f"{', '.join(missing[:5])}{', ...' if len(missing) > 5 else ''}")
        if extra:
            print(f"::warning file={os.path.relpath(filepath)}::"
                  f"{filename} has {len(extra)} stale key(s) no longer in en.json: "
                  f"{', '.join(extra[:5])}{', ...' if len(extra) > 5 else ''}")
        for key, message in errors.items():
            print(f"::warning file={os.path.relpath(filepath)}::"
                  f"{filename}:{key}: {message}")

    markdown = build_markdown(summary_rows, any_drift)

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "w", encoding="utf-8") as f:
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

    # Translation findings are informational, not a merge gate.
    return 0


if __name__ == "__main__":
    sys.exit(main())
