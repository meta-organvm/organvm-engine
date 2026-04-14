# Prompt Pipeline Architecture

## Two-Stage Model

The prompt extraction pipeline operates in two stages with distinct ownership boundaries:

**Stage 1 (Engine):** `organvm_engine.prompts.extractor` handles structured session formats
with stable, well-defined schemas: Claude JSONL, Gemini JSON, Codex JSONL. These are
parsed into `RawPrompt` dataclasses, enriched through `classifier`, `threading`, and
`narrator` into `AnnotatedPrompt` dicts, and emitted as `annotated-prompts.jsonl`.

**Stage 2 (Praxis-Perpetua):** `praxis-perpetua/prompt-corpus/ingest-supplementary.py`
handles supplementary sources with unstable or heterogeneous formats: Paste.app clipboard
exports, ChatGPT markdown/JSON exports, Claude `/export` TXT files, SpecStory markdown
history. It emits `supplementary-prompts.jsonl` using the same dict schema as
`AnnotatedPrompt.to_dict()`.

**Bridge:** `organvm_engine.prompts.supplementary` discovers, loads, and merges the
supplementary JSONL into the engine stream at narration time.

## Interface Contract

The supplementary JSONL file (`supplementary-prompts.jsonl`) must contain one JSON object
per line, following the `AnnotatedPrompt.to_dict()` schema:

```json
{
  "id": "sha256[:12]",
  "source": {
    "session_id": "...",
    "agent": "chatgpt|claude-export|specstory|clipboard/<app>",
    "project_dir": "...",
    "project_slug": "...",
    "timestamp": "ISO-8601 or empty",
    "prompt_index": 0,
    "prompt_count": 1
  },
  "content": {
    "text": "first 10000 chars",
    "char_count": 0,
    "word_count": 0,
    "line_count": 0
  },
  "classification": { ... },
  "signals": { ... },
  "threading": { ... },
  "domain_fingerprint": ""
}
```

The bridge tolerates missing fields and malformed lines (skips them silently). The
minimum requirement is that `content.text`, `raw_text`, or top-level `text` contains
the prompt body.

## Why Not Lift Supplementary Into Engine

Three reasons:

1. **Format instability.** Supplementary sources change format without notice (ChatGPT
   has had at least three export formats). Keeping format-specific parsing outside the
   engine prevents churn in the core package.

2. **Scope containment.** The engine's extraction pipeline is tested against session
   schemas with known invariants. Supplementary sources have no schema contract — they
   require opportunistic parsing with fallbacks, which would pollute the engine's type
   discipline.

3. **Run cadence mismatch.** Supplementary ingestion runs on demand when new exports
   arrive. Engine narration runs as part of regular system operations. The JSONL file
   is the stable interface between two independent run cadences.

## Merge Semantics

- **Deduplication:** SHA-256 of the first 200 characters of prompt text. Engine prompts
  take priority (their hashes are registered first).
- **Sort order:** Timestamp ascending. Entries without timestamps sort to the end.
- **No re-classification:** Supplementary entries retain whatever classification the
  ingest script assigned. The engine does not re-run its classifier on supplementary
  prompts.
