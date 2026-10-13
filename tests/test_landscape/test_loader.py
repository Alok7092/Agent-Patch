import pytest
import io
import csv
from src.landscape.loader import load_spreadsheet, auto_detect_columns


@pytest.fixture
def csv_content():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["System ID", "Description", "Product", "Component", "Version", "Kernel", "Tier", "OS", "DB", "Business Unit", "Contact", "Notes"])
    writer.writerow(["PRD-ECC", "Production ECC", "ECC 6.0", "SAP_BASIS", "7.57", "753", "Prod", "Linux", "HANA", "Finance", "admin@corp.com", ""])
    writer.writerow(["QAS-ECC", "QA ECC", "ECC 6.0", "SAP_BASIS", "7.57", "753", "QA", "Linux", "HANA", "Finance", "admin@corp.com", ""])
    return output.getvalue().encode("utf-8")


class TestAutoDetectColumns:
    def test_detects_standard_headers(self):
        headers = ["System ID", "Description", "Product", "Component", "Version", "Tier"]
        mapping = auto_detect_columns(headers)
        assert mapping["sid"] == "System ID"
        assert mapping["component_code"] == "Component"
        assert mapping["version"] == "Version"
        assert mapping["tier"] == "Tier"

    def test_detects_alternative_headers(self):
        headers = ["SID", "Desc", "SAP Product", "Software Component", "Release", "Environment"]
        mapping = auto_detect_columns(headers)
        assert mapping["sid"] == "SID"
        assert mapping["component_code"] == "Software Component"

    def test_unknown_headers_return_empty(self):
        headers = ["Col A", "Col B", "Col C"]
        mapping = auto_detect_columns(headers)
        assert mapping.get("sid") is None


class TestLoadSpreadsheet:
    def test_load_csv(self, csv_content):
        rows = load_spreadsheet(csv_content, "landscape.csv", column_mapping=None)
        assert len(rows) == 2
        assert rows[0]["sid"] == "PRD-ECC"
        assert rows[0]["component_code"] == "SAP_BASIS"
        assert rows[0]["tier"] == "Prod"

    def test_load_csv_with_custom_mapping(self, csv_content):
        mapping = {
            "sid": "System ID",
            "description": "Description",
            "product": "Product",
            "component_code": "Component",
            "version": "Version",
            "kernel_release": "Kernel",
            "tier": "Tier",
            "os": "OS",
            "db": "DB",
            "business_unit": "Business Unit",
            "basis_contact": "Contact",
            "notes": "Notes",
        }
        rows = load_spreadsheet(csv_content, "landscape.csv", column_mapping=mapping)
        assert len(rows) == 2
        assert rows[0]["component_code"] == "SAP_BASIS"
