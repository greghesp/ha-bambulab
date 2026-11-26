### Contribution

Want to contribute to ha-bambulab? Great! We have a few small asks though!

- Please create your patch PRs against the `main` branch.
- Please name your commits accordingly, and add some context as to what you have added.

NOTE - we did previously use a separate `develop` branch for staging initial checkins. This is being retired.

If you feel this integration was valuable and want to support it in other ways, you can [buy me a coffee](https://Ko-fi.com/adriangarside).
### Before you open a PR

- Run the tests: `tests/run_tests.sh` (or `python -m pytest tests` in an environment with `tests/requirements_ha.txt` installed).
- Run the linter on your changes: `python scripts/lint_changed_lines.py`. It only checks the lines your branch changes, so you won't be asked to fix older code. `--fix` formats those lines for you. It needs [Ruff](https://docs.astral.sh/ruff/) at the version pinned in `pyproject.toml` (`uv tool install ruff==0.17.6` or `pip install ruff==0.17.6`).
- Using an AI coding agent? Point it at [AGENTS.md](AGENTS.md) (Claude Code picks it up through `CLAUDE.md` automatically).
- Fill in the **Tested on** and **Evidence** sections of the PR template. Most changes depend on what one printer model reports, and reviewers usually don't have that printer, so the MQTT payload or debug log is what lets them check your change.
