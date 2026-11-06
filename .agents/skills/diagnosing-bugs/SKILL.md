---
name: diagnosing-bugs
description: Diagnose reproducible bugs, incorrect STAC/OAM results, and performance regressions. Use when something is broken, failing, unexpectedly slow, or producing incorrect geospatial output.
---

# Diagnosing bugs

Work from evidence to cause. Do not start by guessing at a fix.

## 1. Build a feedback loop

Create the fastest reliable check that turns red on the reported symptom. Prefer, in order:

1. A focused unittest at the relevant behavior seam.
2. A small deterministic script using a saved, redacted fixture.
3. An HTTP request against a controlled test server.
4. A browser reproduction with a concrete assertion.
5. A minimal manual reproduction with captured steps and output.

Run the loop at least once before claiming it reproduces the bug. If no safe reproduction is possible, state what is missing and stop short of presenting a hypothesis as a diagnosis.

## 2. Reproduce and minimise

Confirm the loop reproduces the user's actual symptom. Capture the exact error or wrong result. Reduce inputs and steps one at a time until every remaining element is necessary to reproduce it. Preserve a regression fixture when it is safe and non-sensitive.

## 3. Rank hypotheses

List 3–5 falsifiable explanations, ordered by likelihood and cost to test. For each, state what observation would support or reject it. Continue without waiting for a reply unless user knowledge could materially change the ranking.

## 4. Probe one variable at a time

Use the narrowest useful instrumentation. For performance issues, measure a baseline before changing code. Tag temporary logs (for example, `[DEBUG-<short-id>]`) and remove them before completion.

Redact credentials, tokens, signed URLs, private imagery paths, and personal metadata from logs and artifacts before displaying or committing them.

## 5. Fix and lock it down

- Add a regression test at the seam that reproduces the actual failure.
- Confirm the test fails before the fix for the expected reason.
- Apply the smallest safe fix.
- Confirm the regression test passes, then rerun the original reproduction.
- Remove temporary instrumentation and throwaway files.

## Domain-specific checks

- For STAC, distinguish Catalog, Collection, Item, asset, link relation, and advertised search capability. Verify behavior against the relevant STAC specification and provider implementation.
- For OAM, use current HOTOSM source/docs as the authority for uploader and API behavior. Mocked responses prove application handling, not live service behavior.
- For geospatial calculations, preserve CRS assumptions explicitly. Never invent or silently assign a CRS.
- For local imagery workflows, keep raster bytes local unless the user explicitly directs otherwise. Never turn a local path into a public `source_url`.
- Treat incomplete pagination, invalid geometry/bbox, and upstream failures as inconclusive/error states, not as proof that no duplicate exists.

## Completion

Report the reproduction command, observed failure, root cause supported by evidence, regression test, verification results, and remaining unverified live-service or real-imagery checks.

*Adapted from [Matt Pocock's Skills for Real Engineers](https://github.com/mattpocock/skills).*