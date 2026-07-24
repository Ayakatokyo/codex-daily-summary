---
name: codex-daily-summary
description: Use when producing a concise Codex daily report, specified-day report, usage review, or fixed-recipient DingTalk and Feishu delivery for an Asia/Shanghai day.
---

# Codex Daily Summary

Use for a daily Codex report, a specified-day report, a usage review, or a request to send the configured DingTalk and Feishu daily report.

## Workflow

1. Read `references/codex-optimization-rubric.md`. Resolve the requested date in `Asia/Shanghai`; default to today. Create `/tmp/codex-daily-summary/YYYY-MM-DD`.
2. Extract the source into that directory:
   ```sh
   python3 scripts/extract_codex_day.py --date YYYY-MM-DD --timezone Asia/Shanghai --output /tmp/codex-daily-summary/YYYY-MM-DD/source.json
   ```
3. Build `report.md` as fixed Markdown from normalized source data only. Prefer the source's `projects` array: consolidate all same-project threads into one project result before writing `项目进展`, blockers, and next-day tasks. Use the legacy `threads` array only when `projects` is absent. `cwd`, project keys, and absolute local paths are source-only metadata and must never appear in the final `report.md`. Include `# Codex 工作日报 - YYYY-MM-DD` and the guard-required sections: `今日概览`, `项目进展`, `当前阻塞`, `下一日待办`, and `Codex 使用优化建议`. Do not include a `来源索引` section in the final report. Never include raw system, developer, reasoning, environment, or tool content.
   - Write for a busy reviewer: lead with outcomes, not process logs. `今日概览` is 2-4 bullets covering only the day's largest shipped results, validated artifacts, and unresolved risks.
   - In `项目进展`, give each project 1-2 bullets by default: one outcome summary and, only when useful, one validation or delivery note. Add a third bullet only for an active blocker, unmerged risk, or decision the user must make next.
   - Merge repeated threads into one statement; do not list every commit, plan, experiment, command, or handoff unless it changes the current decision.
   - Drop low-signal details: intermediate design docs, rejected visual attempts, packaging commands, duplicated "已推送/工作区干净" notes, and raw test counts. Keep a test count only when it is the strongest evidence for a shipped or risky change.
   - If a project has many completed threads, summarize as "完成 A/B/C，验证通过；下一步 D" rather than preserving chronology.
   - `当前阻塞` contains only active blockers or explicit risks. If there are none, write `无明确阻塞。`
   - `下一日待办` is 3-5 action-oriented bullets, deduplicated across projects, each starting with a verb.
4. Apply the rubric for Codex usage optimization. Normally provide 4-6 evidence-based recommendations, never more than 8; provide fewer than 4 when the evidence is weak. Every recommendation needs priority, sanitized evidence, a concrete action, and an executable example.
5. Validate before sending:
   ```sh
   python3 scripts/report_guard.py --report /tmp/codex-daily-summary/YYYY-MM-DD/report.md
   ```
   Stop on any validation error.
6. Configure the Feishu fixed recipient once with `scripts/configure_feishu.py`; it derives the current verified Feishu account and never accepts a runtime recipient override.
7. Review-only or no-send requests never authorize delivery. Complete the review and show the Markdown/status without running `send_dingtalk.py` or `send_feishu.py`. Only a manual daily summary request, daily report request, or explicit send request authorizes immediate delivery to the fixed configured recipients. Do not condition delivery on a separate delivery request. You do not ask for a second confirmation. Send only the validated Markdown to DingTalk and Feishu independently:
   ```sh
   python3 scripts/send_dingtalk.py --report /tmp/codex-daily-summary/YYYY-MM-DD/report.md --date YYYY-MM-DD --source-digest SOURCE_DIGEST
   python3 scripts/send_feishu.py --report /tmp/codex-daily-summary/YYYY-MM-DD/report.md --date YYYY-MM-DD --source-digest SOURCE_DIGEST
   ```
   A failure or UNKNOWN result on one channel does not suppress the other channel. Never override the bot or recipient at runtime and never send raw JSON.
8. Show the Markdown and independent DingTalk and Feishu statuses. State validation or delivery failures plainly.
