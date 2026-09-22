# SPDX-License-Identifier: AGPL-3.0-only
#!/usr/bin/env python3
"""Validate a locally provisioned bundle without network access or secret output."""
import argparse
import importlib.util
import json
from pathlib import Path

# Load only the standalone signer, not pybambu.__init__ (which imports MQTT
# and can shadow the stdlib select module with HA's select.py platform).
source = Path(__file__).resolve().parents[1] / "custom_components/bambu_lab/pybambu/signing.py"
spec = importlib.util.spec_from_file_location("x1c_signing_validator", source)
signing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(signing)
CommandSigner, CommandSigningError = signing.CommandSigner, signing.CommandSigningError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Owner-only directory containing the three slicer PEM files")
    args = parser.parse_args()
    try:
        signer = CommandSigner(args.directory)
        if not signer.configured:
            print(json.dumps({"valid": False, "reason": "bundle_missing"}))
            return 1
        print(json.dumps({"valid": True, "printer_session_ready": False,
                          "crl_stale": signer.crl_stale,
                          "crl_policy": "reviewed-vendor-crl-v1" if signer.crl_stale else "strict",
                          "valid_until": signer._valid_until.isoformat()}))
        return 0
    except (CommandSigningError, OSError):
        print(json.dumps({"valid": False, "reason": "bundle_rejected"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
