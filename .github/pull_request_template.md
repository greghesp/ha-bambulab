## What this changes

<!-- One or two sentences: what was wrong / missing, and what this PR does about it. -->

Fixes #

## Tested on

<!-- Most changes depend on what a specific printer reports, and reviewers usually
     don't have that printer. Tell us exactly what you ran this against. -->

- **Printer(s):** <!-- e.g. P1S, X1C -->
- **Firmware:** <!-- e.g. 01.08.02.00 -->
- **AMS / accessories (if relevant):** <!-- e.g. AMS 2 Pro, AMS HT, none -->
- **Connection:** <!-- LAN mode / Bambu Cloud -->

## Evidence

<!-- Show the behaviour, so a reviewer can check it without the hardware.
     For anything driven by printer data, paste the relevant part of the MQTT
     payload or a debug log (Settings → Devices & services → Bambu Lab →
     Enable debug logging). Screenshots are fine for UI changes.
     Remove serial numbers, access codes and IP addresses first. -->

<details>
<summary>Payload / log</summary>

```
paste here
```

</details>

## Checklist

- [ ] Tests added or updated for this change (or explained below why not)
- [ ] `python -m pytest tests` passes locally
- [ ] `python scripts/lint_changed_lines.py` is clean
- [ ] New user-facing strings are added to `translations/en.json`
- [ ] Docs updated, or no doc change needed

## Notes for the reviewer

<!-- Anything risky, anything you're unsure about, other printers this might affect. -->
