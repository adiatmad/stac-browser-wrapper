# Plan: Complete and Safe OAM Duplicate Checks

## Design

Keep the implementation in the existing `app.py` hosted-app file to preserve the repository's single-file contract. Add one bounded pagination helper that validates each advertised next link before following it. The helper returns fetched features, pages checked, and whether the search was truncated.

The duplicate checker will compare the provider identifier only with the complete STAC Item ID, retain the existing spatial IoU threshold, and expose incomplete/missing-bbox states explicitly. The UI must not style inconclusive results as ready for submission.

## Risks and mitigations

- **Unexpected pagination URLs:** validate HTTPS, hostname, and exact endpoint path before making a request.
- **Unbounded API traffic:** cap requests at ten pages, preserving the existing 100-item page size.
- **False readiness:** use a distinct inconclusive status and render it as a warning.
- **Architecture drift:** keep helpers inline and add tests that extract the actual application functions without importing Streamlit.
