"""Tests for the Counselor primitive."""

from organvm_engine.primitives.counselor import Counselor
from organvm_engine.primitives.types import (
    Frame,
    FrameType,
    InstitutionalContext,
    PrincipalPosition,
)


def test_counselor_synthesizes_assessments():
    counselor = Counselor()
    context = InstitutionalContext(
        situation="Multiple risks detected",
        data={
            "assessments": [
                {
                    "risk_factors": [
                        {"category": "housing", "description": "Eviction notice", "severity": 0.9, "likelihood": 0.8, "exposure": 0.72, "deadline": "2026-05-01"},
                    ],
                    "opportunity_factors": [],
                    "net_exposure": 0.72,
                    "action_vectors": ["Address housing risk"],
                    "frame_applied": "legal",
                    "confidence": 0.7,
                },
                {
                    "risk_factors": [
                        {"category": "cashflow", "description": "Negative balance", "severity": 0.7, "likelihood": 0.6, "exposure": 0.42},
                    ],
                    "opportunity_factors": [],
                    "net_exposure": 0.42,
                    "action_vectors": ["Address cashflow"],
                    "frame_applied": "financial",
                    "confidence": 0.8,
                },
            ],
        },
    )
    result = counselor.invoke(
        context, Frame(FrameType.STRATEGIC), PrincipalPosition(),
    )

    rec = result.output
    assert rec["recommended_action"] != ""
    assert rec["urgency"] == "immediate"  # high exposure + deadline
    assert len(rec["trade_offs"]) > 0
    assert result.confidence < 0.8  # synthesis penalty


def test_counselor_escalates_on_irreversible():
    counselor = Counselor()
    context = InstitutionalContext(
        data={
            "assessments": [{
                "risk_factors": [
                    {"category": "litigation", "description": "Lawsuit filing", "severity": 0.9, "likelihood": 0.9, "exposure": 0.81},
                ],
                "opportunity_factors": [],
                "net_exposure": 0.81,
                "action_vectors": ["File lawsuit response"],
                "frame_applied": "legal",
                "confidence": 0.6,
            }],
        },
    )
    result = counselor.invoke(
        context, Frame(FrameType.STRATEGIC), PrincipalPosition(),
    )

    assert result.escalation_flag is True
    assert result.output["reversibility"] == "irreversible"


def test_counselor_no_assessments():
    counselor = Counselor()
    context = InstitutionalContext(data={})
    result = counselor.invoke(
        context, Frame(FrameType.STRATEGIC), PrincipalPosition(),
    )

    assert result.confidence <= 0.4
    assert "Insufficient" in result.output["rationale"] or "No" in result.output["recommended_action"]
