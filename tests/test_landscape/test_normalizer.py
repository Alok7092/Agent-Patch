import pytest
from src.landscape.normalizer import (
    normalize_component,
    normalize_version,
    NormalizedEntry,
    normalize_entry,
)


class TestNormalizeComponent:
    def test_already_canonical(self):
        aliases = {"SAP_BASIS": ["SAPBASIS", "SAP BASIS"]}
        assert normalize_component("SAP_BASIS", aliases) == "SAP_BASIS"

    def test_resolves_alias(self):
        aliases = {"SAP_BASIS": ["SAPBASIS", "SAP BASIS"]}
        assert normalize_component("SAPBASIS", aliases) == "SAP_BASIS"

    def test_resolves_with_spaces(self):
        aliases = {"SAP_BASIS": ["SAPBASIS", "SAP BASIS"]}
        assert normalize_component("SAP BASIS", aliases) == "SAP_BASIS"

    def test_unknown_returns_uppercased(self):
        aliases = {"SAP_BASIS": ["SAPBASIS"]}
        assert normalize_component("some_new_comp", aliases) == "SOME_NEW_COMP"


class TestNormalizeVersion:
    def test_dotted_version(self):
        assert normalize_version("7.57") == 757

    def test_integer_version(self):
        assert normalize_version("753") == 753

    def test_three_part_version(self):
        assert normalize_version("7.5.7") == 757

    def test_empty_returns_zero(self):
        assert normalize_version("") == 0

    def test_none_returns_zero(self):
        assert normalize_version(None) == 0


class TestNormalizeEntry:
    def test_full_normalization(self):
        row = {
            "sid": "PRD-ECC",
            "description": "Production ECC",
            "product": "ECC 6.0",
            "component_code": "SAP BASIS",
            "version": "7.57",
            "kernel_release": "753",
            "tier": "Prod",
            "os": "Linux",
            "db": "HANA",
            "business_unit": "Finance",
            "basis_contact": "admin@corp.com",
            "notes": "",
        }
        aliases = {"SAP_BASIS": ["SAP BASIS", "SAPBASIS"]}
        result = normalize_entry(row, aliases)
        assert isinstance(result, NormalizedEntry)
        assert result.component_code == "SAP_BASIS"
        assert result.version_numeric == 757
        assert result.tier == "Prod"
