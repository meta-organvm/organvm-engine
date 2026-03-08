# Plan: Conductor Directive Ingestion Pipeline

**Date**: 2026-03-07
**Status**: IMPLEMENTED

## Summary

Implemented a directive ingestion pipeline that lets the Conductor intercept `ingest:` prefixed user prompts and translate them into structured actions across the system.

## What Was Built

### 1. Hook Directive Detection (Step 1)
**File**: `organvm-iv-taxis/tool-interaction-design/hooks/claude-prompt-gate.sh`
- Added detection for `ingest:`, `research:`, `capture:`, `distill:` prefixes
- Emits `[DIRECTIVE:INGEST]` (etc.) to route through the appropriate conductor tool

### 2. `conductor_ingest` MCP Tool (Step 2)
**File**: `organvm-iv-taxis/tool-interaction-design/mcp_server.py`
- New `ingest()` handler + Tool definition + DISPATCH entry
- Parameters: `content`, `source_agent`, `topic`, `tags` (optional)
- Orchestrates 4 outputs: reference file, alchemia intake, SOP stub, engine guidance
- Dedup via content hash, versioned filenames to prevent clobbering

### 3. Reference File Output (Step 3)
**Target**: `praxis-perpetua/research/YYYY-MM-DD-{slug}.md`
- YAML frontmatter with source, date, topic, tags, content_hash, ingested_via
- Raw content preserved verbatim

### 4. Alchemia Intake Artifact (Step 4)
**Target**: `alchemia-ingestvm/intake/ai-transcripts/YYYY-MM-DD-{slug}.json`
- Compatible with `alchemia intake` crawler
- Includes schema_version, content_preview, status: "intake"

### 5. SOP Stub Generation (Step 5)
**Target**: `organvm-engine/.sops/{slug}.md`
- Follows `_SOP_INIT_TEMPLATE` frontmatter schema
- Discoverable by `organvm sop discover` immediately
- Created: `prompting-standards.md` as initial SOP

### 6. Provider-Aware Prompting Module (Step 6)
**New files**:
- `src/organvm_engine/prompting/__init__.py`
- `src/organvm_engine/prompting/standards.py` — 5 providers as frozen dataclasses
- `src/organvm_engine/prompting/loader.py` — Unified loader + hint formatter

### 7. contextmd Integration (Step 7)
**Modified**:
- `src/organvm_engine/contextmd/generator.py` — `agent` param, `_build_prompting_hint()`
- `src/organvm_engine/contextmd/sync.py` — Passes filename-derived agent to generator

### 8. Tests
- `tests/test_prompting_standards.py` — 26 tests, all passing

## Verification Results

- 26/26 tests pass
- 17/17 contextmd tests pass (no regressions)
- ruff check passes on all modified files
- SOP discovery finds `prompting-standards.md` (scope=system, type=SOP-SKILL)
- `load_guidelines("claude")` and `load_guidelines("GEMINI.md")` work correctly
