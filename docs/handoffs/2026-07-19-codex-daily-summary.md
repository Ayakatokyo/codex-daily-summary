# Codex Daily Summary Skill Handoff

## Objective

Implement and install a personal Codex Skill that manually summarizes the current Mac's daily Codex work, adds evidence-based Codex usage optimization guidance, and immediately sends the finished Markdown to the user's fixed DingTalk account through a configured bot.

## Repository State

- Repository: `/Users/shuzida/Desktop/codex daily summary`
- Branch: `main`
- User explicitly authorized implementation directly on `main`; do not create a worktree.
- Latest commit before this handoff: `c4c25dc docs: plan Codex daily summary skill`
- Implementation has not started. Only the approved design and implementation plan exist.
- The user selected subagent-driven execution. Use a fresh implementer for each task, then a spec-compliance reviewer, then a code-quality reviewer before moving to the next task.

## Source Documents

- Approved design: `docs/superpowers/specs/2026-07-19-codex-daily-summary-design.md`
- Approved implementation plan: `docs/superpowers/plans/2026-07-19-codex-daily-summary.md`

Read both files before implementation. Do not redesign or recreate the plan unless actual code or tool behavior contradicts it.

## Confirmed Product Decisions

1. Trigger is manual, such as “总结今天的 Codex 工作”. There is no scheduler or offline catch-up.
2. Default date range is the current `Asia/Shanghai` day.
3. Read all local Codex workspaces from `~/.codex/sessions`, `~/.codex/archived_sessions`, and a compatible `state_*.sqlite` thread index.
4. Filter system/developer instructions, internal reasoning, environment injection, and raw tool logs. Redact secrets and DingTalk identifiers before synthesis.
5. Group work by project and include overview, completed work, file/code changes, testing, decisions, blockers, and source thread index.
6. “下一日待办” uses `P0`, `P1`, and `P2`; every item includes project and verifiable completion criteria.
7. Codex usage review usually emits 4-6 recommendations, never more than 8, and may emit fewer when evidence is weak.
8. Required optimization dimensions are model/reasoning, prompt quality, context handoff, and continue-versus-new-conversation decisions.
9. Open-ended optimization may also cover task decomposition, Skill/tool/surface selection, verification, parallel work, acceptance criteria, artifacts, feedback loops, and repeated work worth encoding in a Skill, script, or `AGENTS.md`.
10. Every optimization recommendation includes priority, sanitized evidence, concrete action, and an executable example.
11. Once Markdown is generated and validated, send it immediately to the fixed configured DingTalk user. The manual trigger is the send authorization; do not request a second confirmation.
12. Runtime requests cannot override the recipient or bot.
13. `dws chat message send-by-bot` has no server-side UUID/idempotency flag. Use the local delivery ledger. Mark ambiguous timeout/invalid-response results `UNKNOWN` and do not automatically retry.
14. Automated tests must never send a real DingTalk message. The first real delivery occurs only when the user later invokes the installed Skill.

## Verified Local Facts

- Codex thread metadata is available in `~/.codex/state_5.sqlite`; the `threads` table includes title, cwd, rollout path, model, reasoning effort, and archive fields.
- Rollout files contain `response_item` user messages and assistant `final_answer` messages, plus commentary, reasoning, tool calls, and injected context that must be excluded.
- DingTalk current-user query: `/opt/homebrew/bin/dws contact user get-self --format json`.
- DingTalk bot query: `/opt/homebrew/bin/dws chat bot search --format json`.
- Bot send command: `dws chat message send-by-bot --robot-code ... --users ... --title ... --text ... --format json`.
- Multiple bots may require a user selection during configuration. Show only bot names to the user; do not expose IDs or credentials in chat or Git.

## Required Process

The user's `AGENTS.md` requires checking and reading applicable Superpowers skills before every action. For the new implementation conversation:

1. Read `superpowers:subagent-driven-development`.
2. Read `superpowers:writing-skills` and its required `superpowers:test-driven-development` background.
3. Read `superpowers:requesting-code-review` and the subagent prompt templates.
4. Do not use `superpowers:using-git-worktrees` to create isolation; the user explicitly chose direct `main` execution.
5. Follow the implementation plan task by task with RED-GREEN-REFACTOR.
6. For each task: implementer subagent -> spec reviewer -> code-quality reviewer -> fix/re-review until approved.
7. Use `superpowers:verification-before-completion` before completion claims.
8. Use `superpowers:finishing-a-development-branch` after all tasks and final review, while preserving the user's direct-main choice.

## Immediate Next Action

Start Task 1 from the implementation plan: create the three Skill pressure scenarios, run fresh subagents without the new Skill, and record genuine RED baseline behavior. Do not scaffold or write the Skill before those baseline failures are observed.

## New Conversation Starter

Use this as the first message in the new Codex conversation:

```text
继续实现 Codex 每日工作总结 Skill。

仓库：/Users/shuzida/Desktop/codex daily summary
分支：main。已明确授权直接在 main 上执行，不创建 worktree。
执行方式：子代理驱动。

请先完整读取：
1. docs/handoffs/2026-07-19-codex-daily-summary.md
2. docs/superpowers/specs/2026-07-19-codex-daily-summary-design.md
3. docs/superpowers/plans/2026-07-19-codex-daily-summary.md

设计和计划已经确认，代码实现尚未开始。按计划从 Task 1 的 Skill RED 基线压力测试开始，持续执行到实现、审查、安装和验证完成。遵循 AGENTS.md 中的 Superpowers 规则；每个任务都要经过实现、规格审查和代码质量审查。不要发送钉钉测试消息，真实推送只在我安装后手动触发“总结今天的 Codex 工作”时发生。
```
