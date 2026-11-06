---
name: domain-modeling
description: Clarify STAC Browser and OAM domain language, relationships, and durable architectural decisions. Use when terminology is ambiguous, domain concepts change, or a meaningful architecture decision needs recording.
---

# Domain modelling

Build a shared, precise language for the product. The glossary describes domain concepts, not implementation details. Feature specs remain the authority for requirements; ADRs capture only decisions that are expensive or surprising to reverse.

## Repository layout

- Use the root `GLOSSARY.md` for product language shared across the app.
- Keep feature behavior and acceptance criteria in `specs/<feature>/spec.md` and executable work in `tasks.md`.
- Put durable architecture decisions in `docs/adr/NNNN-short-title.md`, creating the directory only when the first ADR is justified.
- Do not create parallel context maps or duplicate the same decision across several documents.

## Work through ambiguity

1. Read the existing glossary and relevant specs/ADRs.
2. Compare the user's wording with the code and upstream STAC/OAM terminology.
3. Identify overloaded terms and propose one canonical term with a concise definition.
4. Stress-test the distinction with concrete examples, including invalid, incomplete, and edge-case states.
5. Update the glossary as soon as a term is settled.

If the code contradicts the agreed domain meaning, surface the mismatch. Do not silently redefine either the code or the user's terminology.

## Glossary rules

- Define what a concept is in one or two sentences.
- Include only product/geospatial concepts that are specific to this app.
- Record common ambiguous alternatives under `Avoid` only when they cause real confusion.
- Keep implementation names, class names, and transient UI labels out.
- Do not turn the glossary into a specification or design scratchpad.

## ADR threshold

Offer an ADR only when all three are true:

1. The decision is materially costly to reverse.
2. A future maintainer would not infer the reason from the code.
3. The choice followed a genuine trade-off between alternatives.

Keep ADRs short. Include alternatives and consequences only when they preserve useful context. Do not use ADRs to restate routine implementation choices or duplicate Spec Kit records.

*Adapted from [Matt Pocock's Skills for Real Engineers](https://github.com/mattpocock/skills).*