# Codex Daily Summary Feishu Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add enterprise-app Feishu direct-message delivery as a second independent channel for validated Codex daily reports.

**Architecture:** Keep DingTalk intact. Add a Feishu configuration script that derives a fixed current-user `open_id` from verified `lark-cli` authentication, plus a Feishu sender with a separate local ledger and stable Lark idempotency keys. The Skill invokes the two senders independently after report validation.

**Tech Stack:** Python 3 standard library, `lark-cli`, existing report guard, `unittest` with injected runners, Codex Agent Skill Markdown.

---

### Task 1: Add Feishu Configuration and Delivery Tests

**Files:**
- Modify: `tests/test_feishu_delivery.py`

- [ ] **Step 1: Write failing configuration and delivery tests**

Create tests that dynamically load `configure_feishu.py` and `send_feishu.py` and prove: successful verified auth config writes only `recipientOpenId` and `timezone`; an unverified auth envelope fails; a Feishu command uses `--as bot`, the configured `--user-id`, `--markdown`, and a stable idempotency key; a successful digest is skipped on the second call; a timeout creates `UNKNOWN` and a second call invokes no runner.

- [ ] **Step 2: Run RED**

Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_feishu_delivery -v`.

Expected: module loading fails because the Feishu scripts do not exist.

### Task 2: Implement Feishu Configuration and Sender

**Files:**
- Create: `skill/codex-daily-summary/scripts/configure_feishu.py`
- Create: `skill/codex-daily-summary/scripts/send_feishu.py`
- Modify: `tests/test_feishu_delivery.py`

- [ ] **Step 1: Implement the minimal configurator**

Implement `configure()` with injectable runner. It runs `lark-cli auth status --json --verify`, requires a successful verified user envelope with `identities.user.openId`, and atomically writes mode-`0600` `${XDG_CONFIG_HOME:-~/.config}/codex-daily-summary/feishu-config.json`. It never prints IDs or accepts recipient overrides.

- [ ] **Step 2: Implement the minimal sender**

Implement `deliver()` with report-guard validation, heading-aware chunks, independent `feishu-state.json` ledger, stable `codex-daily-summary:feishu:{date}:{digest}:{part}` idempotency keys, `PENDING` prewrite, and the four delivery states. Build only `lark-cli im +messages-send --as bot --user-id <configured> --markdown <body> --idempotency-key <key> --format json`.

- [ ] **Step 3: Run GREEN**

Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_feishu_delivery -v`.

Expected: all new tests pass without invoking `lark-cli`.

- [ ] **Step 4: Commit**

```bash
git add skill/codex-daily-summary/scripts/configure_feishu.py skill/codex-daily-summary/scripts/send_feishu.py tests/test_feishu_delivery.py
git commit -m "feat: add Feishu daily report delivery"
```

### Task 3: Wire the Skill and Verify Both Channels

**Files:**
- Modify: `skill/codex-daily-summary/SKILL.md`
- Modify: `tests/test_skill_contract.py`

- [ ] **Step 1: Write failing Skill contract assertions**

Require the Skill to mention `configure_feishu.py`, `send_feishu.py`, independent DingTalk and Feishu statuses, and the rule that one channel failure does not suppress the other.

- [ ] **Step 2: Run RED**

Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_skill_contract -v`.

Expected: failures for the absent Feishu workflow phrases.

- [ ] **Step 3: Update the Skill workflow**

Keep review-only/no-send behavior. For an authorized report, validate once, invoke both fixed senders independently, show statuses, and do not retry `UNKNOWN`. Do not permit runtime recipient overrides.

- [ ] **Step 4: Run GREEN and full verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
uv run --with pyyaml python3 /Users/shuzida/.codex/skills/.system/skill-creator/scripts/quick_validate.py skill/codex-daily-summary
```

Expected: all tests and Skill validation pass without real delivery.

- [ ] **Step 5: Commit**

```bash
git add skill/codex-daily-summary/SKILL.md tests/test_skill_contract.py
git commit -m "feat: send daily reports to Feishu and DingTalk"
```

### Task 4: Install and Configure Without Sending

**Files:**
- Copy: `skill/codex-daily-summary/` to `/Users/shuzida/.agents/skills/codex-daily-summary/`
- Create outside repo: `${XDG_CONFIG_HOME:-~/.config}/codex-daily-summary/feishu-config.json`

- [ ] **Step 1: Install the verified Skill copy**

Copy the Skill only after the full suite and repository Skill validator pass.

- [ ] **Step 2: Run no-send Feishu configuration**

Run `python3 /Users/shuzida/.agents/skills/codex-daily-summary/scripts/configure_feishu.py`. This reads verified auth status and writes the fixed current-user Feishu config; it must not send a message.

- [ ] **Step 3: Verify private configuration without printing IDs**

Check that `feishu-config.json` has a non-empty `recipientOpenId`, `Asia/Shanghai` timezone, and `0600` mode. Do not print its contents.

- [ ] **Step 4: Report live boundary**

Do not send a test message. The first manual authorized daily report will attempt both configured channels.
