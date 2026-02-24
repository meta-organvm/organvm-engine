"""Pitch deck generator — template-driven single-HTML pitch decks.

Generates self-contained docs/pitch/index.html files for ORGANVM repos,
themed per organ via the cascading aesthetic system (taste.yaml ->
organ-aesthetic.yaml). Follows the contextmd/ pattern: walk workspace,
load registry + seeds + aesthetic data, generate files, write to repos.

Auto-generated decks are marked:
    <!-- ORGANVM:PITCH:AUTO v1.0 generated 2026-02-24T12:00:00Z -->

Files without this marker are bespoke (hand-crafted) and never overwritten.
"""

PITCH_MARKER = "<!-- ORGANVM:PITCH:AUTO"
PITCH_VERSION = "1.0"
