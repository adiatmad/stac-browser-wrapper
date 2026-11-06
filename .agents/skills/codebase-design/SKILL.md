---
name: codebase-design
description: Design maintainable Python modules and test seams for the STAC Browser. Use when changing module boundaries, reducing coupling, improving testability, or considering a refactor.
---

# Codebase design

Aim for deep modules: a small, clear interface that hides a coherent amount of behavior. Good design improves caller leverage, maintainer locality, and testability.

## Shared vocabulary

- **Module**: a function, class, package, or cohesive slice with an interface and implementation.
- **Interface**: everything a caller must know, including parameters, invariants, ordering, failure modes, configuration, and performance expectations.
- **Depth**: the amount of useful behavior available through that interface.
- **Seam**: the place where behavior can be substituted or observed without changing the caller.
- **Adapter**: a concrete implementation that satisfies an interface at a seam.
- **Leverage**: capability gained by callers per unit of interface they must learn.
- **Locality**: how well related changes, knowledge, and verification stay in one place.

## Design tests

- Prefer a narrow interface that represents a real product concept, not a generic wrapper around one function.
- Keep network, filesystem, and external-service behavior at explicit seams.
- Inject external dependencies when doing so reduces coupling without spreading plumbing across callers.
- Return explicit result states for meaningful outcomes such as complete, inconclusive, unavailable, and failed.
- Keep validation and safety invariants close to the operation they protect.
- Use the deletion test: if removing a wrapper merely moves complexity to every caller, it may be earning its keep; if complexity disappears, it may be a pass-through.

## Project constraints

The hosted app currently has a single-file Streamlit contract. Do not split `app.py`, introduce project-specific imports, or add a runtime dependency solely to make the architecture look cleaner. Change that constraint only when a feature spec explicitly authorizes it and the deployment/test implications are understood.

Do not introduce an abstraction for a hypothetical second implementation. One adapter is evidence of a possible seam; two materially different adapters are stronger evidence that the seam is real.

## When proposing a refactor

Explain the current friction, the proposed interface, what complexity moves behind it, how callers/tests become simpler, and the migration risk. Prefer one small vertical slice over a broad rewrite.

*Adapted from [Matt Pocock's Skills for Real Engineers](https://github.com/mattpocock/skills).*