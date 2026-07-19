# Codex Daily Summary Feishu Delivery Design

## Goal

Extend the installed Codex Daily Summary Skill with a second delivery channel. A manually authorized daily report sends the validated Markdown to both the fixed DingTalk recipient and the current authenticated Feishu account by enterprise-app bot direct message.

## Scope

- Keep DingTalk configuration and delivery behavior unchanged.
- Add a Feishu configurator that reads the current authenticated user from `lark-cli auth status --json --verify` and stores that user's `open_id` locally.
- Add a Feishu sender that uses `lark-cli im +messages-send --as bot --user-id <open_id> --markdown <report> --idempotency-key <stable-key>`.
- Keep a Feishu-specific local ledger with `PENDING`, `SENT`, `FAILED`, and `UNKNOWN` records. The Feishu CLI's idempotency key is deterministic; local `UNKNOWN` is still never retried automatically.
- Change the Skill workflow so an authorized daily report attempts both channels and shows a separate status for each. A failure on one channel does not roll back or suppress the other.
- Tests inject a command runner and never invoke real `lark-cli` message delivery.

## Configuration

Feishu configuration lives at `${XDG_CONFIG_HOME:-~/.config}/codex-daily-summary/feishu-config.json`, mode `0600`, with a private directory mode `0700`.

```json
{
  "recipientOpenId": "verified-current-user-open-id",
  "timezone": "Asia/Shanghai"
}
```

The configuration command does not accept a recipient override. It verifies successful `lark-cli auth status --json --verify` output, requires a verified user identity with a non-empty `openId`, and never prints IDs. It does not send a test message. Application-bot availability, message permission, and app visibility are diagnosed only when a real daily report is later delivered.

## Delivery

`send_feishu.py` accepts the final Markdown, report date, source digest, fixed config path, and fixed ledger path. It first validates the Markdown with `report_guard.py`, then chunks it with the same heading-aware rules as DingTalk.

For every chunk, its key is `{date}:{digest}:{part}`. The sender records `PENDING` before invoking `lark-cli`; explicit nonzero or negative response becomes `FAILED`; timeout, interruption, or invalid JSON becomes `UNKNOWN`; a successful response records `SENT` with `sentAt`. Existing `SENT` chunks are skipped; `PENDING` and `UNKNOWN` chunks raise without a new send.

The CLI command uses `--as bot`, `--user-id` from configuration, `--markdown`, `--idempotency-key`, and `--format json`. Runtime flags never override the recipient. The idempotency key is stable and channel-specific, for example `codex-daily-summary:feishu:{date}:{digest}:{part}`.

## Skill Flow

For a manual daily-summary, daily-report, or explicit send request, the Skill generates and validates one report, then invokes DingTalk and Feishu delivery independently. It reports each channel as `SENT`, `SKIPPED`, `FAILED`, or `UNKNOWN`.

If Feishu is unconfigured, DingTalk still proceeds and Feishu is reported as configuration failure. If DingTalk is unconfigured, Feishu still proceeds. Review-only and no-send requests invoke neither sender. The request is the authorization for the configured destinations only; there is no second confirmation and no runtime recipient override.

## Testing

- Feishu config test: only a successful verified auth envelope produces a private config; malformed, unverified, or missing `openId` is rejected.
- Feishu sender tests: fixed user command construction, deterministic idempotency key, `SENT` deduplication, `UNKNOWN`/`PENDING` no-retry behavior, and failure isolation.
- Skill contract tests: both delivery scripts, independent channel statuses, and no-send behavior are present.
- Full test suite uses fake runners. No real Feishu or DingTalk message is sent while developing or validating.

## Non-goals

- Group destinations, Webhooks, bot creation, or changing the configured recipient at report time.
- Retrying ambiguous delivery outcomes.
- Refactoring the existing DingTalk sender into a generic multi-channel abstraction.
