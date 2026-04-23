"""Storage contract tests for stateful institutional primitives."""

from pathlib import Path

import pytest

from organvm_engine.primitives.archivist import ArchivistStore
from organvm_engine.primitives.guardian import GuardianState
from organvm_engine.primitives.inst_ledger import LedgerStore
from organvm_engine.primitives.mandator import MandatorStore
from organvm_engine.primitives.storage import (
    institutional_store_root,
    primitive_store_dir,
    stateful_primitive_names,
)


def test_institutional_store_root_defaults_to_home_directory():
    assert institutional_store_root() == Path.home() / ".organvm" / "institutional"


def test_stateful_primitives_have_dedicated_store_directories():
    root = institutional_store_root()

    assert stateful_primitive_names() == (
        "guardian",
        "ledger",
        "archivist",
        "mandator",
    )
    assert primitive_store_dir("guardian") == root / "guardian"
    assert primitive_store_dir("ledger") == root / "ledger"
    assert primitive_store_dir("archivist") == root / "archivist"
    assert primitive_store_dir("mandator") == root / "mandator"


def test_stateful_store_classes_use_shared_contract():
    assert GuardianState()._base == primitive_store_dir("guardian")
    assert LedgerStore()._base == primitive_store_dir("ledger")
    assert ArchivistStore()._base == primitive_store_dir("archivist")
    assert MandatorStore()._base == primitive_store_dir("mandator")


@pytest.mark.parametrize("primitive_name", ["assessor", "counselor"])
def test_assessor_and_counselor_are_stateless(primitive_name):
    with pytest.raises(ValueError, match="stateless or unknown"):
        primitive_store_dir(primitive_name)
