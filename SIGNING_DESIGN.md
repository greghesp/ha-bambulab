# Signed cloud fan controls — experimental design for review

This draft demonstrates opt-in signed/encrypted fan commands on cloud-paired
X1C firmware. **It is not a turnkey HACS release or a request to merge before
the architecture, licensing and credential lifecycle are agreed.**

## Evidence and credit

The deployed development build used ha-bambulab 2.2.25, Home Assistant 2026.9.1
on ARM64, and an X1C on firmware 01.12.00.00 with cloud MQTT and Developer LAN
Mode off. An idle-printer chamber-fan test observed 0 → 20 → 0% in both the
fan entity and the separate printer speed sensor. Restoration was confirmed.
The part-cooling and auxiliary entities were available but were not separately
actuated in that controlled test. The owner subsequently confirmed the controls
worked in normal use. No claim is made for other printer models or firmware.

This review branch ports that implementation onto current `main`; it is not a
snapshot of the operator's installation. Its tests use generated fixtures and
mocked clients, and it has not replaced the working installation.

Protocol credit belongs to [Open Bamboo Networking](https://github.com/ClusterM/open-bamboo-networking),
particularly research/06.02-mqtt.md and research/10.02–10.04. Local credential
acquisition used [BambuSlicerKeySaver](https://github.com/danielwoz/BambuSlicerKeySaver).
No claim is made to have discovered Bambu's signing protocol.

## Behavior

- Native part-cooling, auxiliary and chamber fan controls and ordinary HA fan
  actions; no heatbreak control or additional motion/heater entities.
- Missing or invalid optional signing material leaves telemetry working.
- `security.app_cert_install` provisioning correlates responses; device trust
  is invalidated on disconnect and re-established for the next session.
- G-code uses encrypted `param_enc` only, never plaintext `param` alongside it.
  The exact serialized payload and byte length are signed with RSA/SHA-256.
- Command IDs are reserved durably under a process lock before publication;
  they do not reset at reconnect/restart or wrap at 30000.
- Unavailable authorization and failed publication propagate errors to HA.
  Authorization rejection triggers reprovisioning, **not command replay**.
- Signed fan state comes from printer telemetry, not an optimistic override.
  Slicer G-code may overwrite a requested speed during printing.

## Credential and operational boundary

The prototype reads operator-provided `slicer_key.pem`, `slicer_cert.pem` and
`slicer_crl.pem` from `/config/.storage/bambu_lab_signing/PRINTER_SERIAL/`.
It requires a private directory and regular owner-only, non-symlink files.
Preserve `sequence.json` and its lock across restarts and credential rotation.
`python tools/check_signer.py /path/to/private/bundle` validates offline and
returns only status, not key contents. No account token, device identity,
credential, proprietary binary, capture, or deployment receipt is supplied.

**Provisioning is not renewal.** Session provisioning is implemented, but
vendor credential refresh, onboarding/repair UX and renewal are unresolved.
Without acceptable material, controls remain unavailable.

### Stale vendor CRL: explicit limitation

Two official Linux plugin versions supplied the same signed CRL beyond its
`nextUpdate`. That is not evidence of fresh revocation status. Strict expiry
validation is the default. The hardware proof used a private, explicitly
reviewed compatibility receipt, pinning the exact certificate and CRL hashes
for at most 30 days. Signature, certificate validity, key matching and known
revocation checks still apply, but later revocations cannot be ruled out.
No operator's receipt or hashes are included. This policy is included for
honest review, **not proposed as an automatically renewed default**.

## Licensing and maintainer decisions

The signing module, signing fixtures and standalone validator are supplied
under AGPL-3.0-only (`COPYING.signing`). Existing upstream MIT notices remain
intact; this draft does not silently claim those additions are MIT or relicense
the upstream project. Distribution of a combined work needs the corresponding
AGPL obligations considered before merge.

The preferred topic for maintainer feedback is an independently packaged AGPL
signer companion with a narrow transport boundary, versus a separately
maintained AGPL fork. A process boundary alone does not settle licensing.
An in-process merge should wait for an explicitly acceptable licensing basis.

Other decisions before readiness:

1. Credential acquisition, rotation, revocation and repair ownership.
2. Trust validation for device certificates and provisioning replies.
3. Explicit user opt-in and supported-model/capability gating.
4. Whether any bounded stale-CRL policy is acceptable at all.
5. Reboot/reconnect/rejection behavior and broader hardware coverage.

## Tests

`python -m pytest tests/pybambu -q` exercises the existing regression suite and
generated signing fixtures (encryption, signatures, CRLs, permissions,
correlation, sequence persistence/concurrency, rejection and no replay).
`python -m pytest tests/test_fan_entity.py -q` runs additional mocked entity
checks when Home Assistant is installed; otherwise those checks skip.
No test needs vendor credentials, makes a service call or controls a printer.
