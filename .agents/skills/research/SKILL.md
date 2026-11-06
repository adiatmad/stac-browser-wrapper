---
name: research
description: Research STAC, OAM, geospatial imagery, dependencies, and external API behavior using primary sources. Use when a change depends on external contracts, current documentation, or technical facts that must be verified.
---

# Technical research

Research the source that owns the behavior. Prefer official specifications, first-party API documentation, upstream source code, release notes, and reproducible experiments. Use secondary articles only to discover leads or explain context.

## Workflow

1. State the exact question and the implementation decision it may affect.
2. Identify the authoritative source: STAC specification/extensions, HOTOSM/OpenAerialMap code and docs, Streamlit/Python package docs, GDAL documentation, or the actual provider API.
3. Read the relevant source section or code path, including version and date where available.
4. Cross-check critical claims against a second primary source or a minimal reproducible request when practical.
5. Record uncertainty, version differences, and whether the claim is documented, observed, or inferred.
6. Save substantial findings in `docs/research/<topic>.md` with source links, access date, concise conclusions, and implications for this app. For a small one-off fact, cite it in the spec/PR instead of creating a file.

## STAC/OAM safeguards

- Distinguish normative STAC behavior from provider-specific behavior and this app's implementation.
- Do not infer support for POST search, extensions, authentication, pagination, or asset access unless the source explicitly establishes it.
- Treat OAM uploader and API contracts as versioned and deployment-dependent.
- Do not publish local paths, private imagery, credentials, or user metadata in research notes.
- Do not make live-service claims from mocked tests or documentation alone. Label what was actually observed.

## Output

Give a short answer first, then evidence-backed findings, source links, date/version context, implementation implications, and unresolved questions. If research drives a code change, translate the conclusion into a spec/acceptance criterion before implementation.

*Adapted from [Matt Pocock's Skills for Real Engineers](https://github.com/mattpocock/skills).*