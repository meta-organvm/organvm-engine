"""Tests for ontology/taxonomy.py — stratified entity taxonomy (SPEC-001)."""

import pytest

from organvm_engine.ontology.taxonomy import (
    CATEGORY_MAP,
    EntityCategory,
    EntitySubCategory,
    classify,
    is_dependent,
    is_independent,
    is_occurrent,
)

# ── CATEGORY_MAP completeness ───────────────────────────────────────


class TestCategoryMap:
    """Verify the category map covers all known entity types."""

    KNOWN_ENTITY_TYPES = {"organ", "repo", "module", "document", "session", "variable", "metric"}

    def test_all_known_types_are_mapped(self):
        assert set(CATEGORY_MAP.keys()) == self.KNOWN_ENTITY_TYPES

    def test_all_values_are_valid_enum_tuples(self):
        for entity_type, (cat, sub) in CATEGORY_MAP.items():
            assert isinstance(cat, EntityCategory), f"{entity_type}: bad category"
            assert isinstance(sub, EntitySubCategory), f"{entity_type}: bad subcategory"

    def test_map_is_not_empty(self):
        assert len(CATEGORY_MAP) > 0


# ── classify() ──────────────────────────────────────────────────────


class TestClassify:
    def test_organ_is_independent_continuant(self):
        cat, sub = classify("organ")
        assert cat == EntityCategory.CONTINUANT
        assert sub == EntitySubCategory.INDEPENDENT_CONTINUANT

    def test_repo_is_independent_continuant(self):
        cat, sub = classify("repo")
        assert cat == EntityCategory.CONTINUANT
        assert sub == EntitySubCategory.INDEPENDENT_CONTINUANT

    def test_module_is_independent_continuant(self):
        cat, sub = classify("module")
        assert cat == EntityCategory.CONTINUANT
        assert sub == EntitySubCategory.INDEPENDENT_CONTINUANT

    def test_variable_is_specifically_dependent(self):
        cat, sub = classify("variable")
        assert cat == EntityCategory.CONTINUANT
        assert sub == EntitySubCategory.SPECIFICALLY_DEPENDENT_CONTINUANT

    def test_metric_is_specifically_dependent(self):
        cat, sub = classify("metric")
        assert cat == EntityCategory.CONTINUANT
        assert sub == EntitySubCategory.SPECIFICALLY_DEPENDENT_CONTINUANT

    def test_document_is_generically_dependent(self):
        cat, sub = classify("document")
        assert cat == EntityCategory.CONTINUANT
        assert sub == EntitySubCategory.GENERICALLY_DEPENDENT_CONTINUANT

    def test_session_is_occurrent_process(self):
        cat, sub = classify("session")
        assert cat == EntityCategory.OCCURRENT
        assert sub == EntitySubCategory.PROCESS

    def test_unknown_type_raises_keyerror(self):
        with pytest.raises(KeyError, match="Unknown entity type 'bogus'"):
            classify("bogus")

    def test_empty_string_raises_keyerror(self):
        with pytest.raises(KeyError):
            classify("")

    def test_case_sensitive(self):
        with pytest.raises(KeyError):
            classify("Organ")


# ── is_independent() ────────────────────────────────────────────────


class TestIsIndependent:
    @pytest.mark.parametrize("entity_type", ["organ", "repo", "module"])
    def test_independent_types(self, entity_type: str):
        assert is_independent(entity_type) is True

    @pytest.mark.parametrize("entity_type", ["variable", "metric", "document", "session"])
    def test_non_independent_types(self, entity_type: str):
        assert is_independent(entity_type) is False


# ── is_dependent() ──────────────────────────────────────────────────


class TestIsDependent:
    @pytest.mark.parametrize("entity_type", ["variable", "metric", "document"])
    def test_dependent_types(self, entity_type: str):
        assert is_dependent(entity_type) is True

    @pytest.mark.parametrize("entity_type", ["organ", "repo", "module", "session"])
    def test_non_dependent_types(self, entity_type: str):
        assert is_dependent(entity_type) is False


# ── is_occurrent() ──────────────────────────────────────────────────


class TestIsOccurrent:
    def test_session_is_occurrent(self):
        assert is_occurrent("session") is True

    @pytest.mark.parametrize(
        "entity_type",
        ["organ", "repo", "module", "document", "variable", "metric"],
    )
    def test_continuants_are_not_occurrent(self, entity_type: str):
        assert is_occurrent(entity_type) is False


# ── Enum values ─────────────────────────────────────────────────────


class TestEnumValues:
    def test_category_enum_values(self):
        assert EntityCategory.CONTINUANT.value == "CONTINUANT"
        assert EntityCategory.OCCURRENT.value == "OCCURRENT"
        assert EntityCategory.ABSTRACT.value == "ABSTRACT"

    def test_subcategory_enum_count(self):
        """Ensure all 9 subcategories are defined."""
        assert len(EntitySubCategory) == 9

    def test_subcategory_continuant_members(self):
        assert EntitySubCategory.INDEPENDENT_CONTINUANT.value == "INDEPENDENT_CONTINUANT"
        assert (
            EntitySubCategory.SPECIFICALLY_DEPENDENT_CONTINUANT.value
            == "SPECIFICALLY_DEPENDENT_CONTINUANT"
        )
        assert (
            EntitySubCategory.GENERICALLY_DEPENDENT_CONTINUANT.value
            == "GENERICALLY_DEPENDENT_CONTINUANT"
        )

    def test_subcategory_occurrent_members(self):
        assert EntitySubCategory.PROCESS.value == "PROCESS"
        assert EntitySubCategory.EVENT.value == "EVENT"
        assert EntitySubCategory.TEMPORAL_REGION.value == "TEMPORAL_REGION"

    def test_subcategory_abstract_members(self):
        assert EntitySubCategory.GOVERNANCE_OBJECT.value == "GOVERNANCE_OBJECT"
        assert EntitySubCategory.CAPABILITY.value == "CAPABILITY"
        assert EntitySubCategory.TYPE.value == "TYPE"


# ── Partition properties ────────────────────────────────────────────


class TestPartitionProperties:
    """Every entity type belongs to exactly one category partition."""

    def test_independent_and_dependent_are_disjoint(self):
        for entity_type in CATEGORY_MAP:
            assert not (
                is_independent(entity_type) and is_dependent(entity_type)
            ), f"{entity_type} is both independent and dependent"

    def test_continuant_and_occurrent_are_disjoint(self):
        for entity_type in CATEGORY_MAP:
            cat, _sub = classify(entity_type)
            if cat == EntityCategory.CONTINUANT:
                assert not is_occurrent(entity_type)
            elif cat == EntityCategory.OCCURRENT:
                assert is_occurrent(entity_type)

    def test_every_continuant_is_independent_or_dependent(self):
        for entity_type in CATEGORY_MAP:
            cat, _sub = classify(entity_type)
            if cat == EntityCategory.CONTINUANT:
                assert is_independent(entity_type) or is_dependent(entity_type), (
                    f"{entity_type} is continuant but neither independent nor dependent"
                )
