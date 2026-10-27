# Engineering workflow for this repository

This project uses an evidence-first workflow for AI-assisted changes.

## Delivery loop

**define the job → collect the evidence → parse the docs → save the memory → compress the context → run the code safely → watch what changes → ship the output**

### 1. Define the job
- State the user outcome and the smallest useful scope.
- Record explicit non-goals.
- Do not turn a request into a larger product without evidence.

### 2. Collect the evidence
- Inspect the current repository before proposing edits.
- For OAM behavior, verify against the current HOTOSM/OpenAerialMap code or documentation.
- For raster behavior, prefer real GDAL output and real imagery test cases over assumptions.
- Mark uncertain behavior as uncertain; never present an inference as a verified requirement.

### 3. Parse the docs
- Extract only the rules that affect the current task.
- Prefer authoritative upstream behavior over generic GIS conventions when the goal is OAM compatibility.
- Keep source URLs/paths in the feature notes when a decision depends on them.

### 4. Save the memory
- Keep durable decisions in the feature specification and task notes.
- Record important constraints, rejected approaches, and unresolved questions.
- Do not rely on chat history as the only record of an implementation decision.

### 5. Compress the context
Before implementation, reduce the task to:
- outcome
- acceptance criteria
- evidence
- constraints
- current files
- test cases
- open risks

Avoid copying large unrelated files or logs into prompts/work items.

### 6. Run code safely
- Work on a feature branch.
- Prefer small, reviewable commits.
- Never overwrite user imagery in generated GDAL commands.
- Never invent CRS information.
- Validate generated commands before presenting them as ready to run.
- Keep local-only imagery workflows local; do not upload source imagery merely for validation.

### 7. Watch what changes
After implementation:
- inspect the diff
- run focused tests
- test the real workflow where possible
- compare behavior before/after
- investigate failures instead of masking them

A successful code write is not evidence that the feature works.

### 8. Ship the output
A feature is not done until:
- acceptance criteria are checked
- tests or manual verification are recorded
- known limitations are documented
- user-facing instructions are accurate
- no unsupported claims such as “guaranteed OAM upload” are made

## Anti-slop delivery gate

Use the anti-slop principle as a filter, not a visual style guide:
- no invented facts, metrics, screenshots, success claims, or requirements
- no decorative UI added without a user/job reason
- no generic explanatory copy when a concrete instruction is possible
- no duplicate abstractions when an existing project helper is sufficient
- no large refactor when a focused change solves the stated problem
- every new UI element must have a job and a testable state

For UI work, perform a final human-oriented pass for clarity, keyboard/focus behavior, error states, empty states, and mobile/reflow behavior where applicable.

## Spec Kit alignment

For non-trivial features, follow this sequence:

1. specify — define the user outcome and acceptance criteria
2. clarify — resolve material ambiguity
3. plan — choose the smallest architecture consistent with evidence
4. checklist — define verification gates
5. tasks — break implementation into small executable units
6. analyze — check consistency and risks before coding
7. implement — make the smallest safe change
8. converge — verify the delivered behavior against the specification

For small maintenance changes, use the same principles without creating ceremony that adds no value.

## Superpowers-inspired execution layer

Use this layer to make the existing evidence-first and Spec Kit workflow more executable. It complements the rules above; it does not replace them, add an application/runtime dependency, or require ceremony for trivial edits.

### Before implementation
- Inspect repository state, applicable instructions, relevant code/tests, and current failures before asking questions or editing.
- State the job, acceptance criteria, constraints, and non-goals. Ask one focused question only when a material decision cannot be resolved from repository evidence.
- For substantial or behavior-changing work, compare meaningful implementation options, recommend the smallest sound option, and record the approved design plus a short, testable plan in the relevant spec/tasks.
- Analyze the plan against existing architecture, safety invariants, and acceptance criteria before coding.

### Implementation and debugging
- Prefer test-first red/green/refactor: add or update a focused failing test, make the smallest change that passes, then refactor while keeping tests green. Do not manufacture a failing test when a useful regression test is not feasible; state why and use the strongest available verification.
- For failures, reproduce first, inspect the earliest relevant error and trace the root cause. Form and test one evidence-based hypothesis at a time; do not mask errors, weaken valid assertions, or change tests merely to obtain a green run.
- Keep changes small and independently verifiable. Use parallel work only for genuinely independent tasks with clear file boundaries and integrate/review their outputs before relying on them.
- Follow repository-specific safety rules, including local-first imagery handling and explicit user-controlled OAM publication.

### Review and convergence
- Review the complete diff for scope, accidental deletions, duplicated abstractions, secrets, destructive side effects, and mismatch with the approved spec.
- Run focused tests after each meaningful change, then the relevant full test suite and available real-workflow checks. Inspect actual exit status/logs; a successful edit or an unrelated green workflow is not proof.
- Separate automated-test evidence from deployment, browser, real-service, and real-imagery acceptance. Mark inaccessible checks as blocked/unverified and identify the exact evidence needed.
- Complete both a spec-compliance review (every acceptance criterion and invariant) and a code-quality/safety review before declaring done. Record remaining limitations and the next concrete action.

### Method and tool boundaries
- Apply these practices through the supported instructions/skills of the active coding environment when available; do not assume a particular skill installer or add Superpowers as a runtime package.
- Keep Spec Kit as the repository's durable source of scope, decisions, and acceptance criteria; use this execution layer for disciplined implementation, debugging, and review. Anti-Slop and Loop & Graph remain delivery gates.

## Agency Agents specialist routing

Use the upstream Agency Agents catalog as an optional set of task-specific perspectives, not as a second mandatory process or a claim of autonomous execution. Activate only the roles that address the current risk; do not run every specialist on every change. Keep Spec Kit as the durable source of requirements and acceptance criteria, Superpowers as the execution discipline, and Anti-Slop plus Loop & Graph as delivery gates.

### Routing rules

- **Product Manager** — For a new feature, unclear user problem, or materially ambiguous success criteria. Produce a concise problem statement, user outcome, measurable acceptance criteria, scope, and non-goals. Source: https://github.com/msitarzewski/agency-agents/blob/main/product/product-manager.md
- **Minimal Change Engineer** — For bug fixes, maintenance, or risk of unrelated refactoring. Prefer the smallest justified diff; record useful out-of-scope improvements separately instead of sneaking them into the patch. Source: https://github.com/msitarzewski/agency-agents/blob/main/engineering/engineering-minimal-change-engineer.md
- **Code Reviewer** — For behavior-changing code and pre-delivery review. Return one complete, prioritized set of actionable findings about correctness, regressions, maintainability, security, and test coverage; do not spend review effort on stylistic preferences already enforced by tools. Source: https://github.com/msitarzewski/agency-agents/blob/main/engineering/engineering-code-reviewer.md
- **AI-Generated Code Security Auditor** — For credentials, authentication/authorization, untrusted input, external integrations, sensitive data, or security-relevant dependency/configuration changes. Tie each finding to concrete code/evidence, impact, and remediation. Do not invent vulnerabilities or pad findings to meet a quota. Source: https://github.com/msitarzewski/agency-agents/blob/main/security/security-ai-generated-code-auditor.md
- **Evidence Collector / Reality Checker** — For acceptance and release readiness. Map requirements to appropriate evidence, report reproducible deviations, state what was actually tested, and list remaining unverified/blocked checks. Combine both perspectives in one verification pass unless separate evidence collection and certification are genuinely needed. Sources: https://github.com/msitarzewski/agency-agents/blob/main/testing/testing-evidence-collector.md and https://github.com/msitarzewski/agency-agents/blob/main/testing/testing-reality-checker.md

### Boundaries and non-duplication

- These links are references to upstream guidance; this repository does not vendor or copy full persona prompts, install the whole catalog, add an agent runtime, or imply these personas are installed in every coding environment.
- Do not duplicate Spec Kit specifications/tasks, Superpowers design/test/debug/review steps, or existing CI. A specialist perspective should improve the relevant existing step, not create a parallel checklist by default.
- Keep test-first implementation, root-cause debugging, full-diff review, and verification-before-completion from the Superpowers-inspired layer in force.
- Security reviews must be proportional to the change and evidence-based. QA screenshots may prove appearance, but behavior needs assertions, recorded outcomes, or reproducible steps too.
- Keep the single-file hosted app contract, local-first imagery processing, preservation of local data, and explicit user-controlled OAM publication unchanged.
- Treat automated CI, live Streamlit startup, browser acceptance, external-service behavior, and real-imagery results as distinct evidence categories. Never infer one from another.
