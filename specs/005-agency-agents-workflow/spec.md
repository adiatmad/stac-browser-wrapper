# Feature Specification: Agency Agents Specialist Routing

**Status:** Documentation integration implemented on `docs/agency-agents-workflow`. Diff and scope reviewed; CI passed on commit `e42ab07bfb334c85bfbbe8f21090c4e8796a4eea`. An independent GitHub review is still outstanding; keep this PR draft and unmerged until review and final-head CI are confirmed.

## 1. User outcome

Make product planning, implementation, review, security, QA, and delivery more reliable by invoking a small set of relevant Agency Agents perspectives at the right points in the existing repository workflow—without duplicating the frameworks already in use.

## 2. Design decision

Use a lightweight repository-local routing guide that links to the upstream Agency Agents source files and defines the task triggers and expected outputs. Do not copy full persona prompts or install the entire catalog. Spec Kit remains the durable specification process; Superpowers remains the execution discipline; Anti-Slop and Loop & Graph remain delivery gates.

## 3. Constraints and non-goals

- Keep the existing single-file hosted app contract (`app.py`) unchanged.
- Do not add runtime dependencies, agent frameworks, secrets, credentials, or tool-specific installer assumptions.
- Do not claim the upstream personas are installed or execute autonomously; this integration is guidance for the active coding workflow.
- Do not require every specialist for every task; apply only relevant roles.
- Do not create duplicate planning, test, security, or review ceremonies when existing project steps already satisfy the need.
- Preserve local-first imagery workflows and explicit user-controlled OAM publication.
- Keep this change documentation/specification-only.

## 4. Specialist routing

- **Product Manager** — trigger: new feature, unclear user problem, or materially ambiguous success criteria. Output: problem statement, user outcome, measurable acceptance criteria, scope and non-goals.
- **Minimal Change Engineer** — trigger: bug fix, maintenance, or a risk of unrelated refactoring. Output: smallest justified implementation and separately recorded follow-up ideas.
- **Code Reviewer** — trigger: behavior-changing code or pre-delivery review. Output: evidence-backed, prioritized, actionable findings about correctness, regressions, maintainability, security, and tests.
- **AI-Generated Code Security Auditor** — trigger: credentials, authentication/authorization, untrusted input, external integrations, sensitive data, or security-relevant dependency/configuration changes. Output: evidence-backed findings with impact and remediation; no speculative alarms.
- **Evidence Collector / Reality Checker** — trigger: acceptance and release readiness. Output: requirement-to-evidence mapping, reproducible failures, tested scope, and explicit unverified or blocked checks. Combine their perspectives in one verification pass unless separate evidence collection and certification are genuinely needed.

Upstream sources:
- Product Manager: https://github.com/msitarzewski/agency-agents/blob/main/product/product-manager.md
- Minimal Change Engineer: https://github.com/msitarzewski/agency-agents/blob/main/engineering/engineering-minimal-change-engineer.md
- Code Reviewer: https://github.com/msitarzewski/agency-agents/blob/main/engineering/engineering-code-reviewer.md
- AI-Generated Code Security Auditor: https://github.com/msitarzewski/agency-agents/blob/main/security/security-ai-generated-code-auditor.md
- Evidence Collector: https://github.com/msitarzewski/agency-agents/blob/main/testing/testing-evidence-collector.md
- Reality Checker: https://github.com/msitarzewski/agency-agents/blob/main/testing/testing-reality-checker.md

## 5. Acceptance criteria

- [x] `AGENTS.md` defines activation triggers, expected outputs, and the boundaries between Agency Agents, Spec Kit, Superpowers, Anti-Slop, and Loop & Graph.
- [x] Every selected upstream specialist is linked to its canonical source; no full persona prompt is copied into the repository.
- [x] The guide makes specialist use task-triggered and allows shared verification to avoid duplicate work.
- [x] Security review requires concrete evidence and remediation, not speculative findings or fixed issue quotas.
- [x] Verification separates automated CI from live deployment, browser, external service, and real-data acceptance.
- [x] Diff is limited to `AGENTS.md` and this feature's Spec Kit specification/task checklist relative to the Superpowers workflow branch.
- [x] GitHub Actions tests workflow passed on commit `e42ab07bfb334c85bfbbe8f21090c4e8796a4eea` (run [39871158983](https://github.com/adiatmad/stac-browser-wrapper/actions/runs/39871158983)); the final checklist update triggers a fresh run, which must be checked against the final PR head before merge.
- [x] No app code, dependencies, credentials, local imagery, cache, or output data are changed.

## 6. Verification record

1. Re-fetched the current branch's `AGENTS.md`, this specification, and task checklist.
2. Reviewed the full PR #11 patch. The routing is optional and task-triggered; it avoids duplicating Spec Kit, Superpowers, Anti-Slop, and Loop & Graph. No runtime code or dependencies are introduced.
3. Confirmed the PR changed-file list is exactly `AGENTS.md`, `specs/005-agency-agents-workflow/spec.md`, and `specs/005-agency-agents-workflow/tasks.md`.
4. GitHub Actions run [39871158983](https://github.com/adiatmad/stac-browser-wrapper/actions/runs/39871158983) completed successfully for commit `e42ab07bfb334c85bfbbe8f21090c4e8796a4eea`. Check the new workflow run generated by the final checklist commit before merge.
5. No GitHub review submissions were present at the time of this check. This self-review is not a substitute for an independent review.
6. This documentation-only PR does not establish live Streamlit startup, browser acceptance, external-service behavior, or real-imagery acceptance for the separate hosted-app work.
