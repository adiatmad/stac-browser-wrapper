---
name: pr
description: Prepare a clear, evidence-based pull request for STAC Browser changes. Use when creating or improving a PR title/body or preparing a branch for review.
---

# Pull request writing

Keep the PR body short and make the important change easy to understand. Use the user's domain language and link the originating spec.

## Required sections

### Summary

Describe the user outcome and the smallest useful view of the change. Choose one: a short call-flow, data-flow, file-responsibility tree, or focused diff sketch. Do not add a diagram when two sentences are clearer.

### Evidence

List only evidence that exists:

- focused and full test commands with actual results;
- CI workflow/run links and job outcomes;
- desktop/mobile browser evidence for UI changes;
- live STAC/OAM or real-raster checks only when actually performed.

Distinguish mocked regression coverage from live-service verification. Never imply that a green CI run proves upstream service availability or successful imagery publication.

### Merge danger

State whether the change is easy to roll back or materially irreversible, then describe the blast radius. Explicitly call out any impact on local raster privacy, public source URLs, upload/publication behavior, STAC discovery, or OAM metadata when relevant.

## Quality bar

- Link the spec and key upstream contract sources.
- Include known limitations and unverified checks.
- Do not claim the PR is ready to merge until the diff, required checks, and review state have been inspected.
- Do not merge or push to `main` unless the user explicitly authorizes it.

*Adapted from [Matt Pocock's Skills for Real Engineers](https://github.com/mattpocock/skills).*