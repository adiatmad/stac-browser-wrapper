# Feature Specification: Native Streamlit Workbench Theme

**Status:** Implemented; automated verification pending  
**Branch:** `feature/streamlit-workbench-design`

## Problem

The workbench already has task-oriented navigation, shadcn display components, and separated source panels. A previous app-wide CSS redesign was rolled back after readability feedback. The next visual improvement should therefore use Streamlit's supported theme configuration rather than another stylesheet or frontend layer.

## User outcome

Users get a consistent, restrained, high-contrast light interface while retaining the existing Streamlit workflows and familiar controls.

## Design decision

Use the native `.streamlit/config.toml` theme:
- Light page background: `#FFFFFF`.
- Secondary surface: `#F1F5F9`.
- Main text: `#0F172A`.
- Primary accent: `#0F766E`.
- Sans-serif system font.

The accent is selected to retain a clear teal identity while maintaining at least 4.5:1 contrast against white for normal-sized text. The main text color also exceeds the same contrast threshold against both surfaces.

## Acceptance criteria

1. Streamlit loads the theme from `.streamlit/config.toml` without runtime dependencies.
2. Theme text/accent combinations meet WCAG AA 4.5:1 contrast against their intended backgrounds.
3. No global CSS injection, remote fonts, custom JavaScript, or additional UI framework is introduced.
4. Existing two-workflow navigation, shadcn components, source selection, STAC discovery, S3 browsing, spatial filtering, Tasking Manager/JOSM handoff, OAM duplicate checking, local GDAL preflight, and manual publication boundary remain unchanged.
5. Existing widget keys and workflow state contracts remain unchanged.
6. Existing unit tests and desktop/mobile Playwright smoke checks pass.
7. Visual acceptance is reported separately from unit tests; if screenshots cannot be inspected, that limitation is stated.

## Non-goals

- Rewriting the app or moving away from Streamlit.
- Reworking STAC/OAM behavior, metadata, validation, or network requests.
- Reintroducing the previous Hallmark global stylesheet.
- Adding new features, dependencies, or a GitHub Pages frontend.
- Merging the change or deploying a production configuration without review.
