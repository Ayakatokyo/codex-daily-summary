# Codex Optimization Rubric

Every recommendation must include a priority, sanitized evidence, a concrete action, and an executable example. Base all observations on normalized extracted data only.

## Model and reasoning

Recommend a model or reasoning approach only when the day's evidence shows a task-size or reliability mismatch. Do not invent model names, releases, capabilities, or performance claims. Use a verified current model when available; otherwise use the capability profiles `daily-fast` for routine, bounded work and `complex-deep` for multi-step, high-risk, or ambiguous work.

## Prompt quality

Check whether prompts preserve the user's goal, constraints, success criteria, authority boundaries, and requested output. Recommend a concise goal-first prompt with acceptance checks when evidence shows ambiguity, scope drift, or repeated clarification. Do not replace the user's objective with a generic workflow.

## Context handoff

Assess whether the next turn has the goal, decisions, changed files or data, validation evidence, open risks, and next action. Recommend a compact handoff when a thread loses these facts or work moves between people or sessions. Keep evidence sanitized and specific to the source.

## Conversation boundary

Recommend continuing the current conversation when its context remains relevant and the next action is a direct continuation. Recommend a new conversation when scope, audience, authority, repository, or objective changes materially. A new-conversation handoff must include the objective, current state, constraints, evidence, files or artifacts, unresolved risks, and the first next action.

## Open-ended review

Review evidence-only signals across task decomposition, tool sequencing, verification, error recovery, security and privacy, delivery discipline, context size, repetition, and user alignment. Do not infer hidden intent or claim unsupported causes. Prefer a smaller set of high-signal recommendations over filler.
