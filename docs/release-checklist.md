# Release checklist — publishing artifacts under the two-axis discipline

The npm release of `@maskshell/solidforge` shipped with a wrong license
declaration (MIT instead of Apache-2.0) because publishing was treated as a
mechanical task instead of a disciplined artifact: no fetched-source check, no
adversarial review, no frozen checklist. This file is the frozen blueprint
(bc) for every future publish. A publish is a RELEASE, and releases go
through the same gates as code.

## Gate 0 — deterministic (inner ring, CI suite 55)

`scripts/check-release-metadata.py` must pass before ANY publish attempt. It
asserts, mechanically:

- package name `@maskshell/solidforge`, license `Apache-2.0`, semver version;
- `files` whitelist ships `lib`, `README.md`, `LICENSE`, `NOTICE`;
- shipped `LICENSE`/`NOTICE` byte-identical to the repo root copies;
- README license footer agrees with `package.json`;
- `.github/workflows/publish.yml` in trusted-publishing posture
  (`id-token: write`, no token secret).

A red Gate 0 blocks the publish, period. It does not replace the outer-ring
checks below — it only guarantees the mechanical consistency class that bit
us.

## Gate 1 — psv (fetched-source verification, before every publish)

Each of the following is a CLAIM that must be adjudicated against its primary
source, not memory:

- **License**: repo `LICENSE` (and upstream `maskshell/solidforge`'s license
  via `api.github.com/repos/maskshell/solidforge`) — fetched and read, not
  recalled. Record: license text present, SPDX id, copyright line.
- **Name/scope ownership**: `registry.npmjs.org/-/org/<scope>/user` — the
  scope exists and the publishing account is a member.
- **Name collision (pas)**: the exact package name is available or owned by
  us; deliberate scoped naming preferred over squatting unscoped names.
- **2FA/publish policy**: account publish-2FA mode (npm docs/changelog) and
  the credential path chosen (OTP / GAT / trusted publishing) — the policy
  evolves (2026-07-31 restriction), so re-fetch each time.

## Gate 2 — csr (adversarial review of the release artifact)

The diff being released (package.json, README, `lib/`, workflow, checklist
itself) goes through the `cross-source-review` skill with a fresh-context
reviewer before the publish step. The reviewer's findings are disposed
honestly (fix / reject / escalate); the convergence record is kept in the
release trail. This is where MIT-vs-README-class contradictions are caught by
a second source instead of by the consumer.

## Gate 3 — the publish procedure (frozen order)

1. Bump version in `packages/solidforge-plugin/package.json` (x.y.z).
2. Gates 0–2 green.
3. Publish via trusted publishing (tag `v<x.y.z>` → CI) — or, when OIDC is
   not yet configured, the explicitly documented manual fallback
   (`npm publish --otp=…` or a GAT, per the current policy).
4. Verify the registry: `npm view` name/version/license/dist-tags + the
   tarball endpoint (new scopes can lag on the packument — re-check, do not
   re-publish blindly; if republishing is unavoidable, bump the version).
5. Update the upstream Discussion/issue trail with the new version and any
   findings.

## Incident record

- 2026-08-14: `@maskshell/solidforge@0.1.0` published with `license: MIT`
  while the repo/upstream are Apache-2.0. Root cause: no release gate
  existed; the claim went unverified and was caught by human review. Fixed in
  0.1.2 (Apache-2.0, LICENSE/NOTICE shipped); Gate 0 added as the
  deterministic backstop; this checklist freezes the outer-ring procedure.
