# Feature Specification: Agency Agents Specialist Routing

**Status:** Implementation in progress on `docs/agency-agents-workflow`; awaiting CI and review.

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
- **Code Reviewer** — trigger: behavior-changing code or pre-delivery review. Output: prioritized, actionable findings about correctness, regressions, maintainability, security, and tests.
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

- [ ] `AGENTS.md` defines activation triggers, expected outputs, and the boundaries between Agency Agents, Spec Kit, Superpowers, Anti-Slop, and Loop & Graph.
- [ ] Every selected upstream specialist is linked to its canonical source; no full persona prompt is copied into the repository.
- [ ] The guide makes specialist use task-triggered and allows shared verification to avoid duplicate work.
- [ ] Security review requires concrete evidence and remediation, not speculative findings or fixed issue quotas.
- [ ] Verification separates automated CI from live deployment, browser, external service, and real-data acceptance.
- [ ] Diff is limited to `AGENTS.md` and this feature's Spec Kit specification/task checklist relative to the Superpowers workflow branch.
- [ ] Repository CI passes for the latest PR commit, or the exact unavailable/pending state is recorded honestly.
- [ ] No app code, dependencies, credentials, local imagery, cache, or output data are changed.

## 6. Verification plan

1. Inspect existing repository instructions and the current PR stack before edits.
2. Review the selected upstream files and confirm each link points to the intended specialist.
3. Re-fetch the changed files and inspect the complete diff against the Superpowers workflow branch.
4. Confirm the changed-file list contains only the three intended documentation/specification paths.
5. Inspect CI for the latest commit; distinguish a prior green run from a run covering the current head.
