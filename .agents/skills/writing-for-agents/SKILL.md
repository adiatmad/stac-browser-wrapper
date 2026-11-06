---
name: writing-for-agents
description: Write or revise agent-facing instructions, repository skills, and engineering workflow documentation. Use when editing AGENTS.md, skill files, or documents that guide future coding agents.
---

# Writing for agents

Write instructions as an executable workflow, not as an essay. The goal is predictable behavior with the minimum always-loaded context.

## Design the document

1. Identify the job, trigger, inputs, outputs, and completion condition.
2. Put the trigger in the skill description. It is the primary discovery signal.
3. Put ordered actions and hard invariants in `SKILL.md`; move substantial, branch-specific reference material to a nearby file only when it will genuinely be consulted separately.
4. Give each step an observable completion criterion.
5. Use imperative language and concrete verbs. State what the agent should do, what evidence to capture, and when to stop.
6. Separate read-only discovery from mutation. Make approvals and destructive boundaries explicit.
7. Use positive target behavior; retain negative instructions only for hard safety constraints.
8. Keep each rule in one authoritative place. Point to `AGENTS.md`, feature specs, or project config instead of copying their contents.
9. Remove no-op advice, duplicated rules, stale commands, and generic explanations that do not change behavior.

## Progressive disclosure

Keep the always-loaded description short and precise. Keep the main skill focused on the common path. Add references only for a real branch or sequence that would otherwise make the main instructions hard to use.

Before adding a new agent document, search for an existing source of truth and update it when possible. Do not create a second process that competes with Spec Kit, repository instructions, or CI.

## Validation

Check YAML frontmatter, unique skill names, valid relative links, and whether every referenced file exists. Review the final document as a future agent: can it identify when to invoke it, what to do, what not to assume, and how to know it is done?

*Adapted from [Matt Pocock's Skills for Real Engineers](https://github.com/mattpocock/skills).*