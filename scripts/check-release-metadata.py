#!/usr/bin/env python3
"""check-release-metadata.py — the deterministic inner-ring gate for npm
release artifacts (CI suite 55).

Rooted in the 2026-08-14 incident: the package published with
`license: MIT` while the repo and upstream are Apache-2.0 — an unverified
metadata claim that passed every process step and was caught only by human
review. This gate makes that class of failure red at CI time:

- package.json license/name must match the repo's license and identity;
- LICENSE + NOTICE must ship inside the tarball (files whitelist) and match
  the repo root copies byte-for-byte;
- the package README's license footer must agree with package.json;
- the publish workflow must be in the trusted-publishing posture
  (id-token: write, no NODE_AUTH_TOKEN secret) so releases stay OIDC-only.

It deliberately does NOT re-verify the license text itself against the
upstream repo — that is a psv (fetched-source) task on the checklist
(docs/release-checklist.md), not a deterministic assertion.
"""

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PKG_DIR = ROOT / "packages" / "solidforge-plugin"

EXPECTED_NAME = "@maskshell/solidforge"
EXPECTED_LICENSE = "Apache-2.0"
REQUIRED_FILES = ["lib", "README.md", "LICENSE", "NOTICE"]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures = []
    pkg_json = PKG_DIR / "package.json"
    root_license = ROOT / "LICENSE"
    root_notice = ROOT / "NOTICE"

    if not pkg_json.is_file():
        failures.append("packages/solidforge-plugin/package.json missing")
        return report(failures)
    pkg = json.loads(read_text(pkg_json))

    if pkg.get("name") != EXPECTED_NAME:
        failures.append(f"package name {pkg.get('name')!r} != {EXPECTED_NAME!r}")
    if pkg.get("license") != EXPECTED_LICENSE:
        failures.append(
            f"package license {pkg.get('license')!r} != {EXPECTED_LICENSE!r} (repo + upstream are Apache-2.0)"
        )
    if not re.match(r"^\d+\.\d+\.\d+$", str(pkg.get("version", ""))):
        failures.append(f"package version {pkg.get('version')!r} is not x.y.z")
    files = pkg.get("files")
    for required in REQUIRED_FILES:
        if not isinstance(files, list) or required not in files:
            failures.append(
                f"files whitelist must include {required!r} (tarball completeness)"
            )

    if not root_license.is_file():
        failures.append("repo root LICENSE missing")
    else:
        text = read_text(root_license)
        if "Apache License" not in text:
            failures.append("repo LICENSE is not the Apache-2.0 text")
    if not root_notice.is_file():
        failures.append("repo root NOTICE missing")

    # the shipped copies must be byte-identical to the repo copies
    for name in ("LICENSE", "NOTICE"):
        root_copy = ROOT / name
        pkg_copy = PKG_DIR / name
        if root_copy.is_file() and pkg_copy.is_file():
            if read_text(root_copy) != read_text(pkg_copy):
                failures.append(
                    f"packages/solidforge-plugin/{name} drifted from the repo root copy"
                )
        elif root_copy.is_file() and not pkg_copy.is_file():
            failures.append(
                f"packages/solidforge-plugin/{name} missing (must ship in the tarball)"
            )

    # README license footer must agree with package.json
    readme = PKG_DIR / "README.md"
    if readme.is_file() and "Apache-2.0" not in read_text(readme):
        failures.append("package README license footer does not say Apache-2.0")

    # client-half manifest: the registry resolves <pkg>/package.json and the
    # ./client export; both bit us (ERR_PACKAGE_PATH_NOT_EXPORTED + a missing
    # shipped client.js) — the graph silently skips the module otherwise.
    exports_map = pkg.get('exports')
    if not isinstance(exports_map, dict) or './package.json' not in exports_map:
        failures.append('exports must expose ./package.json (client-modules resolves it)')
    if not isinstance(exports_map, dict) or './client' not in exports_map:
        failures.append('exports must expose ./client (the persistent client half)')
    dsh_decl = pkg.get('dsh')
    client_decl = dsh_decl.get('client') if isinstance(dsh_decl, dict) else None
    if not isinstance(client_decl, dict) or client_decl.get('platform') != 'web':
        failures.append('dsh.client must declare platform: web')
    if not (PKG_DIR / 'lib' / 'client.js').is_file():
        failures.append('lib/client.js missing (must ship in the tarball)')

    # publish workflow posture: OIDC, no token secret
    workflow = ROOT / ".github" / "workflows" / "publish.yml"
    if not workflow.is_file():
        failures.append(".github/workflows/publish.yml missing")
    else:
        wf = read_text(workflow)
        if "id-token: write" not in wf:
            failures.append(
                "publish workflow must request id-token: write (provenance/OIDC)"
            )
        if "NODE_AUTH_TOKEN" in wf:
            failures.append(
                "publish workflow must not carry a token secret (trusted publishing only)"
            )

    return report(failures)


def report(failures) -> int:
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("PASS: npm release metadata conforms (name/license/files/README/workflow)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
