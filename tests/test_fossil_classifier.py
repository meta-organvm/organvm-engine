"""Tests for Jungian archetype classifier."""

from organvm_engine.fossil.classifier import classify_commit
from organvm_engine.fossil.stratum import Archetype


def test_shadow_from_fix():
    result = classify_commit("fix: remediate 103 ESLint errors", "fix", "growth-auditor", "III")
    assert result[0] == Archetype.SHADOW


def test_shadow_from_security():
    result = classify_commit("chore: security remediation", "chore", "portfolio", "LIMINAL")
    assert result[0] == Archetype.SHADOW


def test_anima_creative_repo():
    result = classify_commit("feat: Bestiary v1 — 12 mythological beings", "feat", "vigiles-aeternae--theatrum-mundi", "II")
    assert result[0] == Archetype.ANIMA


def test_animus_governance():
    result = classify_commit("feat: temporal versioning for dependency graph", "feat", "organvm-engine", "META")
    assert result[0] == Archetype.ANIMUS


def test_self_testament():
    result = classify_commit("feat: testament self-referential event types", "feat", "organvm-engine", "META")
    assert result[0] == Archetype.SELF


def test_trickster_short_message():
    result = classify_commit("onnwards+upwards;", "", "some-repo", "I")
    assert result[0] == Archetype.TRICKSTER


def test_trickster_no_conventional_prefix():
    result = classify_commit("yolo", "", "some-repo", "II")
    assert result[0] == Archetype.TRICKSTER


def test_mother_ci():
    result = classify_commit("fix: resolve 6 pre-existing BATS CI failures", "fix", "domus", "LIMINAL")
    assert Archetype.MOTHER in result[:2]


def test_father_governance_gate():
    result = classify_commit("feat: individual primacy governance check", "feat", "organvm-engine", "META")
    assert Archetype.FATHER in result[:2]


def test_individuation_cross_organ():
    result = classify_commit("feat: outbound contribution engine", "feat", "orchestration-start-here", "IV")
    assert Archetype.INDIVIDUATION in result[:2]


def test_returns_ranked_list():
    result = classify_commit("feat: add omega criterion #19", "feat", "organvm-engine", "META")
    assert isinstance(result, list)
    assert len(result) >= 1
    assert all(isinstance(a, Archetype) for a in result)


def test_context_sync_is_self():
    result = classify_commit("chore: context sync — refresh auto-generated context files", "chore", "some-repo", "I")
    assert result[0] == Archetype.SELF


def test_sigma_e_father_primary():
    """sigma-E organ boost makes FATHER primary for adjudicatory commits."""
    result = classify_commit(
        "feat: Law 7 enforcement — convergence audit",
        "feat", "system-system--system", "SIGMA_E",
    )
    assert result[0] == Archetype.FATHER


def test_sigma_e_animus_formal():
    """sigma-E organ boost elevates ANIMUS for formal/proof commits."""
    result = classify_commit(
        "feat: axiom proof for dependency graph",
        "feat", "system-system--system", "SIGMA_E",
    )
    assert Archetype.ANIMUS in result[:2]
