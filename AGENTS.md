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
