import pytest
from pathlib import Path


@pytest.fixture
def tmp_db(tmp_path):
    db_path = tmp_path / "test.db"
    return str(db_path)


@pytest.fixture
def config_dir(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    return config


@pytest.fixture
def sample_note():
    return {
        "note_number": "3421384",
        "title": "Security Note: RFC Vulnerability",
        "cvss_score": 8.5,
        "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        "priority": "high",
        "components": ["SAP_BASIS", "BC-MID"],
        "version_ranges": [
            {"component": "SAP_BASIS", "min": 750, "max": 789}
        ],
        "release_date": "2026-06-10",
        "description": "A critical vulnerability in RFC handling allows remote code execution.",
        "solution_type": "patch",
        "related_notes": ["3421000"],
    }


@pytest.fixture
def sample_landscape_entries():
    return [
        {"sid": "PRD-ECC", "component_code": "SAP_BASIS", "version": "757",
         "version_numeric": 757, "tier": "Prod", "product": "ECC 6.0",
         "description": "Production ECC"},
        {"sid": "QAS-ECC", "component_code": "SAP_BASIS", "version": "757",
         "version_numeric": 757, "tier": "QA", "product": "ECC 6.0",
         "description": "QA ECC"},
        {"sid": "PRD-S4H", "component_code": "SAP_BASIS", "version": "789",
         "version_numeric": 789, "tier": "Prod", "product": "S/4HANA 2023",
         "description": "Production S/4HANA"},
        {"sid": "PRD-ECC", "component_code": "KERNEL", "version": "753",
         "version_numeric": 753, "tier": "Prod", "product": "ECC 6.0",
         "description": "Production ECC"},
    ]
