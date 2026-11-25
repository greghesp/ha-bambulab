# AGENTS.md

Guidance for AI coding agents (Claude Code, Codex, Cursor, Copilot and others) working on ha-bambulab. Human contributors should read [CONTRIBUTING.md](CONTRIBUTING.md); everything there applies to agents too.

## What this repo is

A Home Assistant custom integration (`bambu_lab`, installed through HACS) for Bambu Lab 3D printers. It talks to printers over MQTT, either on the LAN or through Bambu Cloud.

## Layout

- `custom_components/bambu_lab/`: the integration itself (config flow, coordinator, and one module per entity platform: `sensor.py`, `switch.py`, `camera.py` and so on).
- `custom_components/bambu_lab/pybambu/`: a plain-Python client library for the printer (MQTT, cloud API, models). It must not import Home Assistant.
- `custom_components/bambu_lab/pybambu/mock_data/`: recorded printer payloads used by the mock MQTT client.
- `custom_components/bambu_lab/translations/`: UI strings. `en.json` is the source.
- `custom_components/bambu_lab/frontend/ha-bambulab-cards.js`: the built Lovelace cards bundle. It is synced from a frontend release; don't hand-edit it.
- `tests/`: integration tests. `tests/pybambu/`: library tests, with real printer payloads as JSON fixtures.
- `scripts/`: maintenance tooling (linting, translation checks, data fetchers).
- `docs/`: user documentation, published with [docs.page](https://use.docs.page) from `.mdx` files and `docs.json`. Use only [docs.page components](https://use.docs.page/components): callouts are `<Info>`, `<Warning>`, `<Error>` and `<Success>` (there is no `<Note>` or `<Tip>`).

## Commands

```bash
python -m pytest tests                  # full suite (needs tests/requirements_ha.txt installed)
tests/run_tests.sh                      # same, in a fresh .venv
tests/run_tests.sh minimum              # against the minimum Home Assistant in hacs.json (needs uv)
python scripts/lint_changed_lines.py    # Ruff on the lines your branch changes; add --fix to format them
python scripts/check_translation_parity.py
```

CI runs the tests twice: against the newest Home Assistant and against the minimum in `hacs.json`, each on the oldest Python that release supports. Code has to work on both. The minimum follows a "last 6 months of releases" policy: a monthly workflow raises it with a PR (`scripts/ha_min_version.py`). Don't use a Home Assistant API newer than the minimum without raising it by hand in the same PR. Ruff is pinned in `pyproject.toml` (`ruff==0.17.6`); use that version.

## Rules

- **Branch from and target `main`.** The old `develop` branch is retired.
- **Commit messages** use Conventional Commits prefixes (`fix:`, `feat:`, `docs:`, `chore:`, `ci:`) and describe the user-visible effect in plain words, e.g. `fix: don't report the printer offline when the connection drops for a moment`.
- **Only lint what you change.** The linter checks changed lines on purpose. Don't reformat untouched code or "clean up" unrelated files; it makes PRs hard to review.
- **Keep `pybambu` free of Home Assistant imports.** Tests live at the repo root, outside `custom_components/`, so collecting them never imports `homeassistant`. Keep it that way.
- **New user-facing strings always go in `translations/en.json`.** Then ask the contributor whether they speak any of the other languages in `translations/` and want to translate the new strings themselves. If they do, add their wording to those locale files exactly as they give it. Any locale left out is filled in later by the auto-translation process, and the parity check only warns, so missing locales don't block the PR. Don't write other locales yourself (machine-translated or not) unless the contributor gave you the text.
- **Add or update tests** for behaviour changes. Printer behaviour differs by model and firmware, so prefer tests driven by a real payload fixture (see `tests/pybambu/*.json`) over hand-built dicts.
- **Don't invent printer fields.** If a change depends on what a printer reports, base it on a real MQTT payload or debug log. If you don't have one, say so in the PR instead of guessing field names or values.
- **Never commit secrets.** Strip serial numbers, access codes, IP addresses and account tokens from fixtures, logs and PR text.

## Pull requests

Fill in every section of [the PR template](.github/pull_request_template.md). In particular:

- **Tested on**: the printer model, firmware and connection the change was actually run against. If it was only tested with unit tests and no real printer, say that plainly.
- **Evidence**: the relevant payload or log excerpt, with identifiers removed.
- **Checklist**: only tick items that were actually done.

If an AI agent wrote a substantial part of the change, say so in "Notes for the reviewer". A human contributor is responsible for reviewing, testing and standing behind every PR they open.
