# Tasks: Superpowers-Inspired Engineering Workflow

Tasks are gated. Do not claim verification without actual evidence.

## 1. Inspect and specify
- [x] 1.1 Inspect repository instructions and existing Spec Kit structure.
- [x] 1.2 Define adoption as repository instructions, not a runtime dependency or assumed universal installer.
- [x] 1.3 Record requirements, non-goals, and acceptance criteria.

## 2. Integrate
- [x] 2.1 Extend `AGENTS.md` with proportional design, test-first implementation, root-cause debugging, diff review, and evidence-based convergence.
- [x] 2.2 Review wording for conflicts or duplication with existing Spec Kit, Anti-Slop, and evidence-first rules. The addition explicitly complements rather than replaces the existing sequence and keeps lightweight work proportional.

## 3. Verify and deliver
- [x] 3.1 Re-fetch the committed file and inspect the final diff. Comparison against `feat/end-to-end-imagery-workflow-spec` showed only `AGENTS.md` and these two Spec Kit files changed.
- [x] 3.2 Inspect PR-triggered CI run [39782779225](https://github.com/adiatmad/stac-browser-wrapper/actions/runs/39782779225): dependency installation and the unit-test step passed on the combined STAC feature + workflow change before this final task-status update.
- [x] 3.3 Confirm no runtime/application files or dependencies changed.
- [x] 3.4 Keep this workstream separate from hosted-acceptance work. PR #8 still has a separate live Streamlit startup/browser acceptance gap; this workflow PR does not close it.
