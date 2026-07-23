# Codex Daily Summary Project Grouping Design

## Goal

Group a day's Codex threads by their normalized absolute working directory (`cwd`) before generating the daily report. The report should summarize all work for each project together while keeping local filesystem paths out of the report.

## Scope

- Preserve the extractor's existing sanitized per-thread output.
- Add a deterministic project grouping to the normalized source JSON.
- Make the daily-summary workflow use the grouped projects as its primary reporting input.
- Keep the existing `threads` field for compatibility with existing consumers and delivery source-digest behavior.

Out of scope: grouping projects by directory name, inferring Git repository roots, or resolving paths that no longer exist.

## Data Contract

The extractor will normalize a thread's `cwd` with `Path.cwd`-independent lexical normalization. A non-empty absolute path is the project key. Relative, empty, malformed, or unavailable paths are assigned to one shared fallback project identified internally as `unidentified`.

The normalized source adds a `projects` array ordered by first matching thread order:

```json
{
  "key": "project:<sha256-prefix>",
  "display_name": "Project <sha256-prefix>",
  "thread_ids": ["..."],
  "threads": ["sanitized thread objects"]
}
```

The path itself is not emitted in `projects`, avoiding disclosure through source artifacts beyond what is already present in legacy `threads`. The final report must never contain `cwd`, a local absolute path, or a project key. It will label projects with the sanitized `display_name` and report their consolidated work.

`source_digest` is calculated from the complete normalized source payload used for reporting, including project membership, so a grouping change produces a new digest.

## Reporting Behavior

The workflow reads `projects` first. For each project, it combines the day's thread messages, deduplicates overlapping outcomes, and produces one project-level progress entry. Blockers and next-day tasks should be consolidated by project when supported by evidence. Threads in the fallback project remain summarized, but their unknown association is not invented or attributed to another project.

If `projects` is absent in an older source artifact, the workflow falls back to its existing per-thread behavior rather than failing.

## Error Handling And Privacy

- Normalization must not require a directory to exist or call `resolve()`, because historical worktrees may have moved or been deleted.
- A path that is not a non-empty absolute path must not be used to merge threads into a known project.
- Thread title hashing, message filtering, secret redaction, and other existing sanitization stay unchanged.
- The report guard gains a check rejecting absolute local paths, including macOS `/Users/...` paths.

## Verification

Automated tests will first fail for these cases, then validate:

1. Two threads with the same absolute `cwd` form one project containing both threads.
2. Similar directory names at different absolute paths remain separate projects.
3. Empty and relative `cwd` values share only the fallback project.
4. Project keys and display names are deterministic and do not disclose the path.
5. Changes to project association change `source_digest`.
6. The Skill contract requires project-first report synthesis and prohibits local paths in the final Markdown.
7. The report guard rejects an absolute local path.
