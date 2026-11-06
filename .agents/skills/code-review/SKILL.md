---
name: code-review
description: Review a branch, pull request, or working diff for correctness, specification compliance, maintainability, and safety. Use before delivery or when asked to review code.
---

# Code review

Review the change against two independent axes. Do not let a strong result on one axis hide a failure on the other.

## 1. Pin the review range

- Use the user's fixed point when supplied.
- Otherwise compare the feature branch with its merge base against `main`.
- Record the exact diff and commit range. Confirm the diff is non-empty and the base resolves.

## 2. Spec compliance

Read the originating feature spec and tasks. Report:

- acceptance criteria that are missing or only partially implemented;
- behavior added outside the requested scope;
- cases where code appears to satisfy the spec but violates its intent;
- tests that do not actually prove the stated behavior.

If no spec exists, state that explicitly. Do not invent requirements to fill the gap.

## 3. Standards and safety

Read `AGENTS.md`, relevant nested instructions, and standards that apply to the changed files. Check for:

- correctness, regressions, error handling, and edge cases;
- duplicated logic, unclear names, needless abstraction, and scattered responsibilities;
- secrets, unsafe URL handling, untrusted input, path traversal, and unsafe redirects;
- local raster data leakage, invented CRS assumptions, and unintended upload/publication behavior;
- pagination bounds and false-success states;
- missing or weak regression tests;
- UI keyboard/focus behavior, empty/error states, and desktop/mobile reflow when UI changes.

Treat design smells as review prompts, not automatic violations. Repository instructions and explicit feature contracts take precedence over generic preferences. Skip issues already enforced by tooling unless the change defeats that enforcement.

## 4. Evidence and findings

Use the strongest available evidence: source lines, tests, reproducible commands, CI results, and relevant upstream contracts. Separate confirmed defects from risks and unverified assumptions.

Prioritise findings by severity and impact. For each finding include the file/line, concrete failure scenario, consequence, and a focused remedy. Do not pad the review with stylistic nits or hypothetical vulnerabilities.

If independent review agents are available, separate spec and standards reviews and reconcile their findings. If they are not available, perform two distinct passes yourself; never claim parallel agents were used when they were not.

## 5. Report

Start with the most important actionable findings. If none are found, say so and state the scope/evidence reviewed. Finish with tests/checks run, checks unavailable, and residual risks. A review is not a certification of live STAC/OAM behavior unless those services were actually exercised.

*Adapted from [Matt Pocock's Skills for Real Engineers](https://github.com/mattpocock/skills).*