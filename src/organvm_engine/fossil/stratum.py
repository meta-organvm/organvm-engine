"""Stratum — data models for the fossil record.

FossilRecord is the atomic unit: one commit, normalized, classified,
and hash-linked to the previous record for tamper evidence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum


class Archetype(str, Enum):
    """Jungian archetypes for classifying system activity."""

    SHADOW = "shadow"
    ANIMA = "anima"
    ANIMUS = "animus"
    SELF = "self"
    TRICKSTER = "trickster"
    MOTHER = "mother"
    FATHER = "father"
    INDIVIDUATION = "individuation"


class Provenance(str, Enum):
    """How the record was obtained."""

    WITNESSED = "witnessed"
    RECONSTRUCTED = "reconstructed"
    ATTESTED = "attested"
    CONDUCTED = "conducted"       # session lifecycle event (conductor)
    FIELDED = "fielded"           # process observation (fieldwork)
    CAMPAIGNED = "campaigned"     # contribution campaign tick (contrib_engine)
    CLOCKED = "clocked"           # scheduled beat fired (atomic clock)


@dataclass
class FossilRecord:
    """One commit, normalized and classified.

    The atomic unit of force in the system. Ticks compose into functions
    (repo·hour), functions into modules (organ·day), modules into beats
    (active days), beats into movements (epochs). The compositional
    hierarchy is: tick → function → module → beat → movement → lifecycle.

    Resonance fields (caused_by, causes, interference) turn this from
    an append-only list into a directed graph of causal force. When an
    organ pipe receives air, the standing wave excites the entire column
    simultaneously — these fields capture the propagation.
    """

    commit_sha: str
    timestamp: datetime
    author: str
    organ: str
    repo: str
    message: str
    conventional_type: str
    files_changed: int
    insertions: int
    deletions: int
    archetypes: list[Archetype]
    provenance: Provenance
    session_id: str | None
    epoch: str | None
    tags: list[str]
    prev_hash: str
    # --- Resonance fields: the pulse propagates ---
    caused_by: str | None = None       # SHA/ID of the record that triggered this one
    causes: list[str] | None = None    # SHAs/IDs of records this one triggered
    interference: list[str] | None = None  # organs affected beyond home organ


def compute_record_hash(record: FossilRecord) -> str:
    """SHA256 of the record's content for chain linking."""
    content = (
        f"{record.commit_sha}|{record.timestamp.isoformat()}"
        f"|{record.organ}|{record.repo}|{record.message}"
        f"|{record.prev_hash}"
    )
    return hashlib.sha256(content.encode()).hexdigest()


def serialize_record(record: FossilRecord) -> str:
    """Serialize to a single JSON line.

    Omits resonance fields when None to keep existing records compact.
    """
    d = asdict(record)
    d["timestamp"] = record.timestamp.isoformat()
    d["archetypes"] = [a.value for a in record.archetypes]
    d["provenance"] = record.provenance.value
    # Omit empty resonance fields for compactness
    for key in ("caused_by", "causes", "interference"):
        if d.get(key) is None:
            d.pop(key, None)
    return json.dumps(d, separators=(",", ":"))


def deserialize_record(line: str) -> FossilRecord:
    """Deserialize from a JSON line.

    Backward-compatible: records without resonance fields get None defaults.
    Records with unknown provenance values fall back to ATTESTED.
    """
    d = json.loads(line)
    d["timestamp"] = datetime.fromisoformat(d["timestamp"])
    d["archetypes"] = [Archetype(a) for a in d["archetypes"]]
    try:
        d["provenance"] = Provenance(d["provenance"])
    except ValueError:
        d["provenance"] = Provenance.ATTESTED
    # Resonance fields — absent in records before this change
    d.setdefault("caused_by", None)
    d.setdefault("causes", None)
    d.setdefault("interference", None)
    return FossilRecord(**d)
