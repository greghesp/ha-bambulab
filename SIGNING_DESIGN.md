# Experimental signed X1C fan controls

This opt-in contribution is open for normal review. It adds part-cooling,
auxiliary and chamber fan controls for secured X1C firmware. Telemetry, camera,
ordinary light traffic and unsigned-printer behavior remain independent.
It does not expose signed heaters, motion, jobs or arbitrary G-code.

**Account login is not signing setup.** Logging into Bambu Cloud supplies an
account token. Fan signing requires a separate operator-provided application
key, certificate chain and current signed revocation list (CRL).

## User workflow

### Account and printer connection

Add the printer normally, or choose **Configure → Account and printer connection**.
The existing wizard requests region, email/phone and password; then an email/SMS
verification code or 2FA code if the vendor requires it. It offers new-code
requests and incorrect/expired-code handling. The user reads the code in their
own mail/SMS/authenticator app; the integration does not access their mailbox.

A printer must match the configured serial exactly. An account without that
printer aborts without updating the entry. Passwords are not put back into an
error form, full entries/authentication responses are not logged, and entering
a flow no longer forces global debug logging.

### First-time signed controls

1. After adding the printer, choose **Configure → Signed fan controls**. This
   menu works without logging in again or re-testing cloud/LAN connectivity.
2. Obtain an export from **your own licensed networking-plugin installation**.
   [BambuSlicerKeySaver](https://github.com/danielwoz/BambuSlicerKeySaver) is the
   external extraction tool used during development; its platform/version
   support is independent of this integration. This PR does not run it,
   distribute vendor keys/binaries, or promise that an export will contain a
   current CRL. Follow the export tool's own instructions and verify its source.
3. Make a ZIP with exactly `slicer_key.pem`, `slicer_cert.pem`, `slicer_crl.pem`
   at its root. No directory wrappers, extra files, links or compatibility
   receipts. Limits: 1 MiB ZIP, 256 KiB per PEM. Stored/Deflate ZIPs only.
4. Open **Import or renew credentials**, select the ZIP and explicitly consent
   to experimental signed fan controls. Use a trusted HTTPS connection to HA.
5. HA validates the complete bundle before replacing any active credentials,
   then reloads this printer entry to establish its signing session. No fan
   command is sent as a test. The controls become available only after the
   printer's certificate exchange succeeds. Observe normal telemetry after any
   separately requested action; broker acceptance is not execution proof.

Only **X1C** may opt in through this workflow/runtime path. Other models retain
normal integration behavior and need independent signing/hardware validation.

### Renewal and repair

The same **Import or renew** action installs a fresh export, preserving the
existing command sequence counter. Account passwords/codes cannot renew these
signing files. There is **no supported automatic vendor-renewal API in this PR**.
If the export source still returns an expired CRL, renewal is unavailable: the
import is rejected and signed controls remain unavailable once their current
credentials expire. No deadline is extended and no stale-CRL bypass is offered
by the UI.

A single entry-scoped HA Repair reports missing/invalid/expired material,
failed printer trust, provisioning required, or expiry within seven days.
The coordinator checks on setup/session changes and every five minutes, even
while the printer is offline. Repairs offer the same import flow, **Retry with
installed credentials**, and **Disable signed fan controls**. Retry validates
current material before reloading; it never replays a fan command. Reload
completion is not printer acceptance, and an unresolved repair is re-created
on the next check. A ready non-expiring signer clears its own repair.

Disabling changes only the signing option, reloads the entry and preserves
account/connection settings, camera, credentials and sequence storage. It blocks future signing before attempting reload (including failed reloads) and does
not change the printer's cloud/LAN mode or physical fan speed.

## Storage and failure behavior

HA's authenticated file-upload selector supplies an opaque ID, not an arbitrary
server path. The upload is consumed/removed on the executor on success,
rejection or declined consent. PEM contents and upload IDs are not put in
config-entry data, options, diagnostics or logs. Cancelled/unsubmitted uploads
are managed by HA's upload lifecycle.

Validation stages files in an owner-only temporary directory. A complete
`credentials.json` snapshot is flushed, fsynced and atomically replaced in
`/config/.storage/bambu_lab_signing/PRINTER_SERIAL/`, with mode 0600 and private
0700 directories. Readers load one generation, never mixed files. Rejected
imports and failures before replacement preserve the previous snapshot;
post-replacement directory-fsync failure is reported as a storage error (the
new snapshot may already be active). The flow never deletes the prior legacy
PEMs, `sequence.json` or its lock. Private HA backups can contain signing
credentials and must be protected accordingly.

The existing three-PEM layout remains readable for older opt-in installations.
Once a managed snapshot exists, it is authoritative: corruption cannot fall
back to older credentials. Invalid optional material leaves read-only
integration behavior intact and signing unavailable. The standalone
`python tools/check_signer.py /path/to/private/bundle` checks either layout
without network access or secret output.

## Cryptographic and command boundary

- Application chains must reach the independently shipped vendor CAs in
  `pybambu/certs/bambu.cert`. An uploaded root cannot add trust. Dates,
  signatures, CA/path-length and key-usage constraints are checked; unsupported
  critical extensions are refused. Only the verified path supplies CRL issuers.
- Provisioning replies must match the pending sequence, succeed, and carry a
  bounded device chain to the independently shipped vendor CAs. Its RSA leaf's
  single common name must exactly match the configured printer serial; CA
  leaves and disallowed key encipherment are refused. This uses the documented
  Bambu CN/serial profile, not a general-purpose hostname verifier. Unknown
  profiles fail closed. Device revocation is not claimed without a device CRL.
- Invalid replies reset session trust. Disconnect/rejection requires a fresh
  correlated exchange; no automatic command replay. Printer-chain expiry also
  caps the session's usable lifetime.
- `publish_fan(FansEnum, percentage)` accepts only the three typed fans and a
  finite 0–100 percentage. The signer constructs one canonical M106 internally,
  preserves existing ten-percent rounding, encrypts `param_enc`, and signs the
  exact serialized bytes. Raw payloads/compound G-code cannot enter this path.
- Sequence IDs are reserved durably under a process lock before publication and
  retained across restart, reconnect and rotation. Publication failure surfaces
  to HA. Fan state comes from telemetry, not optimistic state.

### Historical stale-CRL compatibility

Earlier hardware work encountered two official plugin versions supplying the
same expired CRL. That is not fresh revocation evidence. A legacy, locally
reviewed, exact-bundle-pinned receipt could permit at most 30 days, while still
checking signatures, key matches, certificate validity and known revocations.
The legacy validator retains that behavior for transparent compatibility;
**managed imports and retries require a fresh CRL**, never create/import a
receipt, and managed snapshots cannot use one after expiry. No private receipt
or exception deadline is distributed or extended by this contribution.

## Validation and historical hardware evidence

Tests generate all keys/certificates/CRLs and use mocked transports. Library
coverage includes chain/identity rejection, signing/encryption, revocation,
expiry, permissions, malformed ZIP/snapshot handling, failed atomic replacement,
sequence continuity, correlation, broker errors and no replay. Real HA classes
exercise consent, upload cleanup, options preservation, login challenges,
wrong-account selection, repair ownership/reappearance, and entity behavior.
CI runs the library suite plus HA contracts on the declared minimum HA version
and the current tested HA version. No test needs vendor material or actuates
hardware.

Commands:

```sh
python -m pytest tests/pybambu -q
# In an environment with Home Assistant and the test requirements installed:
python -m pytest tests/test_fan_entity.py tests/test_signing_opt_in.py tests/test_signing_flow.py tests/test_signing_repairs.py -q
```

An earlier build (ha-bambulab 2.2.25, HA 2026.9.1 ARM64, X1C firmware 01.12.00.00)
passed an idle chamber-fan **0 → 20 → 0%** cloud test with independent telemetry
and restoration. Other fans were not separately actuated in that test. It used
the documented legacy CRL exception. That is historical evidence, **not a
hardware test of this revision's trust/credential flow**. No live integration
installation or printer command accompanies this PR update.

## Remaining external gates and licensing

1. Fresh vendor material must actually be obtainable. Guided import/renewal
   does not fix a vendor that supplies stale CRLs, nor does account login.
2. Current-revision hardware proof of the stricter device profile, rotation and
   reboot behavior is still needed; broader models are not enabled.
3. Maintainers must agree to a distribution/licensing basis before merging.
   Signing modules, credential flows, fixtures and validator retain
   **AGPL-3.0-only** notices and `COPYING.signing`; original MIT notices remain.
   This PR does not silently relicense either work. A separate process alone
   would not settle the combined-work question. No maintainer acceptance is
   implied by ready-for-review state or passing checks.

Protocol credit: [Open Bamboo Networking](https://github.com/ClusterM/open-bamboo-networking),
particularly research/10.02–10.04 and the CN/serial device-certificate profile.
Credential acquisition credit: BambuSlicerKeySaver. Independent fan correctness
fixes #2120 were merged separately and are not part of this feature diff.
