---
name: codex-daily-summary
description: Generate a report and Codex usage optimization for today or a specified Asia/Shanghai day, then send it to the configured DingTalk and Feishu recipients.
---

# Codex Daily Summary

Use for a daily Codex report, a specified-day report, a usage review, or a request to send the configured DingTalk and Feishu daily report.

## Workflow

1. Read `references/codex-optimization-rubric.md`. Resolve the requested date in `Asia/Shanghai`; default to today. Create `/tmp/codex-daily-summary/YYYY-MM-DD`.
2. Extract the source into that directory:
   ```sh
   python3 scripts/extract_codex_day.py --date YYYY-MM-DD --timezone Asia/Shanghai --output /tmp/codex-daily-summary/YYYY-MM-DD/source.json
   ```
3. Build `report.md` as fixed Markdown from normalized source data only. Include `# Codex 工作日报 - YYYY-MM-DD` and the guard-required sections: `今日概览`, `项目进展`, `当前阻塞`, `下一日待办`, and `Codex 使用优化建议`. Do not include a `来源索引` section in the final report. Never include raw system, developer, reasoning, environment, or tool content.
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
