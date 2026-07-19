---
name: codex-daily-summary
description: Generate a report and Codex usage optimization for today or a specified Asia/Shanghai day, then send it to the configured DingTalk recipient.
---

# Codex Daily Summary

Use for a daily Codex report, a specified-day report, a usage review, or a request to send the configured DingTalk daily report.

## Workflow

1. Read `references/codex-optimization-rubric.md`. Resolve the requested date in `Asia/Shanghai`; default to today. Create `/tmp/codex-daily-summary/YYYY-MM-DD`.
2. Extract the source into that directory:
   ```sh
   python3 scripts/extract_codex_day.py --date YYYY-MM-DD --timezone Asia/Shanghai --output /tmp/codex-daily-summary/YYYY-MM-DD/source.json
   ```
3. Build `report.md` as fixed Markdown from normalized source data only. Include `# Codex 工作日报 - YYYY-MM-DD` and the guard-required sections: `今日概览`, `项目进展`, `当前阻塞`, `下一日待办`, `Codex 使用优化建议`, and `来源索引`. Never include raw system, developer, reasoning, environment, or tool content.
4. Apply the rubric for Codex usage optimization. Normally provide 4-6 evidence-based recommendations, never more than 8; provide fewer than 4 when the evidence is weak. Every recommendation needs priority, sanitized evidence, a concrete action, and an executable example.
5. Validate before sending:
   ```sh
   python3 scripts/report_guard.py --report /tmp/codex-daily-summary/YYYY-MM-DD/report.md
   ```
   Stop on any validation error.
6. When the user manually requests delivery, that request authorizes delivery: do not ask for a second confirmation. Send only the validated Markdown to the fixed configured recipient:
   ```sh
   python3 scripts/send_dingtalk.py --report /tmp/codex-daily-summary/YYYY-MM-DD/report.md --date YYYY-MM-DD --source-digest SOURCE_DIGEST
   ```
   Never override the bot or recipient at runtime and never send raw JSON.
7. Show the Markdown and delivery status. State validation or delivery failures plainly.
