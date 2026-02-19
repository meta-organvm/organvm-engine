"""CLAUDE.md auto-generator.

Generates and injects system context sections into CLAUDE.md files
across the ORGANVM workspace. Keeps the AI context layer synchronized
with registry-v2.json and seed.yaml contracts.

Auto-generated sections are demarcated:
    <!-- ORGANVM:AUTO:START -->
    ## System Context (auto-generated)
    ...
    <!-- ORGANVM:AUTO:END -->

Anything outside these markers is preserved untouched.
"""

# Marker constants used by generator and sync
AUTO_START = "<!-- ORGANVM:AUTO:START -->"
AUTO_END = "<!-- ORGANVM:AUTO:END -->"
