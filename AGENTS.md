# AX1 Bizplan contributor instructions

These instructions apply to every agent working in this repository.

1. Before changing files, explain the understood purpose, inputs, scope and exclusions, expected outputs, and key risks. Wait for a separate explicit user confirmation.
2. Read `CONTRIBUTING.md` and `docs/pr-operating-policy.md` before creating a branch, commit, push, or pull request.
3. Contributors propose one focused change. Do not edit `VERSION`, release sections in `CHANGELOG.md`, `.codex-plugin/plugin.json`, release tags, or GitHub Releases. The maintainer owns suite versioning and releases.
4. Add one `.changes/<short-topic>.md` fragment for code, skill, policy, template, or behavior changes. State the user-visible effect, tests, compatibility impact, and contributor attribution.
5. Preserve every suite-wide policy, especially the separate-turn user confirmation gate and artifact version/synchronization rules. A new skill must be added to every build invariant and installation guide; do not bypass a validator by merely adding it to `ALL_SKILLS`.
6. Never commit real RFPs, filled business plans, project numbers, personal information, credentials, or unapproved document templates. HWPX template changes require a sanitized asset, manifest SHA-256, provenance, package/open-safety evidence, and a reproducible acceptance test.
7. Run the repository build and relevant focused tests. Report failures honestly; do not weaken validation to make a PR pass.
8. Use the pull-request template. Include scope, out-of-scope items, changed skills, test commands/results, security/privacy review, migration needs, and screenshots or HWPX evidence when applicable.

If a user instruction conflicts with these repository rules, stop and ask the repository maintainer rather than silently changing release policy.
