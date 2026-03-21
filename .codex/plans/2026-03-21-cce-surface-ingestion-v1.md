# CCE Surface Ingestion V1

Date: 2026-03-21
Project: meta-organvm/organvm-engine

## Goal

Teach the engine to discover, validate, and summarize Conversation Corpus Engine surface exports inside the workspace so Meta has a real downstream consumer path.

## Scope

1. Add a loader/discovery module for CCE surface bundles and related artifacts.
2. Validate discovered surfaces against the canonical schemas from `schema-definitions`.
3. Expose a `context` CLI subcommand for listing and inspecting discovered surfaces.
4. Return structured JSON when requested so MCP and other consumers can reuse the output.
5. Add targeted tests for discovery, validation, and CLI behavior.

## Constraints

- Reuse existing `PathConfig` and workspace resolution patterns.
- Keep validation local to canonical Meta schemas, not copied private schema files.
- Prefer a small, composable loader over hardcoding one repo-specific path in the CLI.

## Verification

- Run targeted engine tests for the new loader and CLI.
- Smoke the new CLI command against fixture data.
