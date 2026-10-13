import pytest
from src.landscape.indexer import build_component_index, ComponentIndex, SystemMatch
from src.landscape.normalizer import NormalizedEntry


@pytest.fixture
def sample_entries():
    return [
        NormalizedEntry(sid="PRD-ECC", description="Prod ECC", product="ECC 6.0",
                        component_code="SAP_BASIS", version="7.57", version_numeric=757,
                        kernel_release="753", tier="Prod", os="Linux", db="HANA",
                        business_unit="Finance", basis_contact="admin@corp.com", notes=""),
        NormalizedEntry(sid="QAS-ECC", description="QA ECC", product="ECC 6.0",
                        component_code="SAP_BASIS", version="7.57", version_numeric=757,
                        kernel_release="753", tier="QA", os="Linux", db="HANA",
                        business_unit="Finance", basis_contact="admin@corp.com", notes=""),
        NormalizedEntry(sid="PRD-S4H", description="Prod S4", product="S/4HANA",
                        component_code="SAP_BASIS", version="7.89", version_numeric=789,
                        kernel_release="789", tier="Prod", os="Linux", db="HANA",
                        business_unit="IT", basis_contact="s4admin@corp.com", notes=""),
        NormalizedEntry(sid="PRD-ECC", description="Prod ECC", product="ECC 6.0",
                        component_code="KERNEL", version="753", version_numeric=753,
                        kernel_release="753", tier="Prod", os="Linux", db="HANA",
                        business_unit="Finance", basis_contact="admin@corp.com", notes=""),
    ]


class TestBuildComponentIndex:
    def test_builds_index(self, sample_entries):
        index = build_component_index(sample_entries)
        assert isinstance(index, ComponentIndex)
        assert "SAP_BASIS" in index.components
        assert 757 in index.components["SAP_BASIS"]
        assert 789 in index.components["SAP_BASIS"]

    def test_systems_grouped_by_version(self, sample_entries):
        index = build_component_index(sample_entries)
        systems_757 = index.components["SAP_BASIS"][757]
        sids = [s.sid for s in systems_757]
        assert "PRD-ECC" in sids
        assert "QAS-ECC" in sids

    def test_lookup_within_range(self, sample_entries):
        index = build_component_index(sample_entries)
        matches = index.lookup("SAP_BASIS", min_version=750, max_version=789)
        sids = [m.sid for m in matches]
        assert "PRD-ECC" in sids
        assert "QAS-ECC" in sids
        assert "PRD-S4H" in sids

    def test_lookup_narrow_range(self, sample_entries):
        index = build_component_index(sample_entries)
        matches = index.lookup("SAP_BASIS", min_version=780, max_version=790)
        sids = [m.sid for m in matches]
        assert "PRD-S4H" in sids
        assert "PRD-ECC" not in sids

    def test_lookup_unknown_component(self, sample_entries):
        index = build_component_index(sample_entries)
        matches = index.lookup("UNKNOWN_COMP", min_version=0, max_version=999)
        assert matches == []
