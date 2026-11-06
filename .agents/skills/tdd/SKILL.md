---
name: tdd
description: Apply test-driven development to STAC Browser features and bug fixes. Use when implementing behavior, fixing regressions, or when a change benefits from a focused red-green-refactor loop.
---

# Test-driven development

Use a tight red-green-refactor loop. The goal is a test that proves the user-visible behavior, not a large collection of tests that merely mirrors implementation details.

## Before the first test

1. Read the relevant repository instructions, feature spec, existing tests, and applicable glossary/ADRs.
2. Identify the smallest user-facing behavior and the existing test seam that exercises it.
3. Derive test cases from acceptance criteria and real failure modes. Do not ask the user to approve an obvious seam already specified by the feature contract; ask only when choosing the seam would materially change the design or confidence.
4. Use the repository's current test runner: `python -m unittest discover -s tests -p "test_*.py"`. Do not introduce pytest or another dependency unless the task requires it and the user approves.

## The loop

For each vertical slice:

1. Add one focused regression or behavior test.
2. Run it and confirm it fails for the intended reason. A syntax error or broken fixture is not a meaningful red signal.
3. Make the smallest implementation change that satisfies the test.
4. Run the focused test and confirm it passes.
5. Refactor only when the behavior is green; rerun the focused test after refactoring.
6. Repeat for the next behavior.

Prefer tests through stable public behavior. Where the current single-file Streamlit app has no practical public seam, use the least brittle existing test technique and document its limitation rather than forcing a large architecture refactor solely to satisfy a testing ideal.

## Test quality

- Assert independently known outcomes, not values recomputed by the implementation.
- Test user-observable outcomes, safety invariants, and failure states.
- Mock external services at the network boundary; do not mock internal functions just to make a test pass.
- Include negative and boundary cases for URL validation, pagination limits, raster metadata, and OAM handoffs where relevant.
- Avoid snapshots or call-count assertions unless they protect a real contract.
- Keep each test name focused on a behavior.

## Completion

Run focused tests after each slice, then the full unittest suite and relevant UI/dependency checks. Inspect the actual exit status and failures. Record which checks ran and which could not run; never infer live OAM, STAC, or real-raster correctness from mocked tests alone.

*Adapted from [Matt Pocock's Skills for Real Engineers](https://github.com/mattpocock/skills), for this repository's Python/Streamlit and Spec Kit workflow.*