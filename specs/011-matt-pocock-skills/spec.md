# Feature Specification: Repository Engineering Skills

**Status:** Implemented on feature branch; awaiting CI and review.

## Problem

The repository has strong top-level engineering rules, but they are not available as focused, discoverable, reusable workflows for recurring tasks such as TDD, debugging, domain modelling, design, code review, research, and PR preparation.

## User outcome

Contributors and coding agents can invoke a small set of repository-specific Agent Skills when the relevant task arises, without duplicating or overriding the existing Spec Kit, Anti-Slop, safety, and verification rules.

## Scope

- Add selected, task-specific skills under `.agents/skills/<skill-name>/SKILL.md`, following the Agent Skills format.
- Adapt upstream engineering practices to the existing Python/Streamlit project, test runner, feature specs, and safety constraints.
- Add a concise domain glossary grounded in current README/spec terminology.
- Add only a small routing section to `AGENTS.md`; existing repository rules remain authoritative.
- Attribute the upstream inspiration to Matt Pocock's Skills for Real Engineers.

## Non-goals

- Do not install every skill in the upstream repository.
- Do not add a skill installer, runtime dependency, MCP server, or agent framework.
- Do not duplicate Spec Kit, issue triage, implementation orchestration, or the existing execution checklist.
- Do not change application behavior, split the single-file hosted app, or change OAM upload/publication safeguards.

## Acceptance criteria

1. Skills exist for TDD, bug diagnosis, domain modelling, codebase design, code review, technical research, PR writing, and agent-document writing.
2. Each skill has valid YAML frontmatter with a unique name and a trigger-focused description.
3. Skills use the repository's Python unittest command and do not assume unavailable tools, subagents, or runtimes.
4. Skills preserve the current single-file Streamlit contract and local-first imagery/OAM publication safeguards.
5. The root glossary defines only product/geospatial concepts grounded in existing documentation.
6. `AGENTS.md` routes to the skills by task and clearly states that repository instructions/specs take precedence.
7. Existing application files and runtime dependencies are unchanged.
8. Skill metadata, internal links, and all referenced files are validated; repository-native tests pass.
