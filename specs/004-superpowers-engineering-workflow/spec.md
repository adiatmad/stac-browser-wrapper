# Feature Specification: Superpowers-Inspired Engineering Workflow

**Status:** Draft implementation on `docs/superpowers-workflow-after-stac-acceptance`; awaiting CI/review.

## 1. User outcome

Make the repository's existing engineering principles easier to execute consistently: clarify requirements, design before substantial changes, test-first implementation, root-cause debugging, and evidence-based convergence.

## 2. Constraints and non-goals

- Preserve the evidence-first delivery loop, Spec Kit sequence, Anti-Slop gate, and Loop & Graph principles.
- Apply practices proportionally; trivial maintenance must not require heavyweight ceremony.
- Use repository instructions and supported coding-environment skills as the adoption method.
- Do not add a runtime dependency, install script, tool-specific assumption, duplicate framework, or unrelated application change.
- Do not claim a skill is installed or available in every coding environment.

## 3. Requirements

- **FR-001 — Repository-first:** inspect applicable instructions, code, tests, and current state before editing or asking questions answerable from evidence.
- **FR-002 — Clear contract:** state outcome, acceptance criteria, constraints, and non-goals; resolve material ambiguity before implementation.
- **FR-003 — Proportional design:** for substantial behavior changes, compare meaningful options, recommend one, and record a concise design and testable plan.
- **FR-004 — Test-first:** use red/green/refactor where practical, with a clear explanation when test-first is infeasible.
- **FR-005 — Root-cause debugging:** reproduce failures, investigate evidence, test hypotheses, and do not hide defects by weakening valid tests.
- **FR-006 — Review and convergence:** inspect the full diff, run focused then broader tests, and distinguish CI from live/deployment/real-data acceptance.
- **FR-007 — Preserve current rules:** Spec Kit remains the durable specification process; Anti-Slop and Loop & Graph remain delivery gates.
- **FR-008 — Minimal footprint:** no runtime package, app behavior change, or tool-specific installer is introduced by this workflow integration.

## 4. Acceptance criteria

- [ ] `AGENTS.md` includes the workflow above without removing existing repository rules.
- [ ] Instructions explicitly cover test-first implementation, systematic debugging, spec and code review, and verification honesty.
- [ ] Instructions allow proportional handling of trivial work and state the supported-environment/tool boundary.
- [ ] Diff contains only the intended workflow documentation/specification files relative to the STAC feature branch.
- [ ] Repository CI passes; if CI cannot be run or is unavailable, report that as unverified rather than inferred.
- [ ] No application behavior, runtime dependencies, or local imagery/data are changed.
