"""Report translation keys that are missing or stale relative to en.json.

Non-blocking by design: prints GitHub Actions ::warning:: annotations and a
step-summary table, but always exits 0. The intent is visibility for
reviewers/maintainers, not a merge gate - a PR that only touches English
strings shouldn't be blocked on translations catching up.
"""
import glob
import json
import os
import sys

TRANSLATIONS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                 "custom_components", "bambu_lab", "translations")
)


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

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as f:
            if not any_drift:
                f.write("## Translation parity\n\nAll locales match `en.json`. :white_check_mark:\n")
            else:
                f.write("## Translation parity\n\n"
                        "This is informational only and does not block merging.\n\n"
                        "| Locale | Missing keys | Stale keys |\n"
                        "| --- | --- | --- |\n")
                for filename, missing, extra in summary_rows:
                    f.write(f"| `{filename}` | {len(missing)} | {len(extra)} |\n")
                f.write("\nRun `python3 scripts/auto_translate.py` to fill in missing keys "
                        "(requires network access to Google Translate).\n")

    if not any_drift:
        print("All locales match en.json.")

    # Always succeed - this check is informational, not a merge gate.
    return 0


if __name__ == "__main__":
    sys.exit(main())
