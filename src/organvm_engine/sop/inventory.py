"""Parse the METADOC--sop-ecosystem.md inventory and compare against discovered SOPs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from organvm_engine.paths import corpus_dir
from organvm_engine.sop.discover import SOPEntry

# Matches table rows like: | 1 | `SOP--foo.md` | SOP | ... |
_TABLE_FILE_RE = re.compile(r"\|\s*\d+\s*\|\s*`([^`]+)`\s*\|")

# Only track SOP-pattern filenames for gap analysis
_SOP_LIKE_RE = re.compile(
    r"^(SOP--|sop--|sop-|METADOC--|metadoc--|APPENDIX--|appendix--)",
    re.IGNORECASE,
)

_PRAXIS_METADOC = "praxis-perpetua/standards/METADOC--sop-ecosystem.md"


@dataclass
class AuditResult:
    tracked: list[SOPEntry] = field(default_factory=list)
    untracked: list[SOPEntry] = field(default_factory=list)
    reference_copy: list[SOPEntry] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)  # filenames in inventory but not on disk


def parse_inventory(metadoc_path: Path | None = None) -> set[str]:
    """Extract all filenames mentioned in the METADOC inventory tables.

    Returns a set of filenames (e.g. {'SOP--foo.md', 'METADOC--bar.md'}).
    """
    if metadoc_path is None:
        metadoc_path = corpus_dir().parent / _PRAXIS_METADOC

    if not metadoc_path.is_file():
        return set()

    filenames: set[str] = set()
    with metadoc_path.open(encoding="utf-8") as f:
        for line in f:
            m = _TABLE_FILE_RE.search(line)
            if m:
                name = m.group(1)
                # Only include SOP/METADOC/APPENDIX-pattern files
                if _SOP_LIKE_RE.match(name):
                    filenames.add(name)
    return filenames


def audit_sops(
    discovered: list[SOPEntry],
    metadoc_path: Path | None = None,
) -> AuditResult:
    """Compare discovered SOPs against the METADOC inventory.

    Classification rules:
    - reference_copy: has canonical-location header (pointing to praxis)
    - tracked: filename appears in inventory
    - untracked: filename not in inventory and not a reference copy
    - missing: filename in inventory but not found in discovered set
    """
    inventory = parse_inventory(metadoc_path)
    result = AuditResult()

    discovered_filenames: set[str] = set()
    for entry in discovered:
        discovered_filenames.add(entry.filename)

        if entry.has_canonical_header:
            result.reference_copy.append(entry)
        elif entry.filename in inventory:
            result.tracked.append(entry)
        else:
            result.untracked.append(entry)

    # Check for inventory entries not found on disk
    for inv_name in sorted(inventory):
        if inv_name not in discovered_filenames:
            result.missing.append(inv_name)

    return result
