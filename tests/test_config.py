import pytest
from pathlib import Path
from src.shared.config import load_config, load_rules, load_component_map, Settings, RulesConfig


def test_load_config_returns_settings(tmp_path):
    settings_yaml = tmp_path / "settings.yaml"
    settings_yaml.write_text("""
app:
  name: "Test App"
  mode: "local"
  secret_key: "test-secret"
  debug: true
database:
  path: "data/test.db"
ingestion:
  schedule_cron: "0 9 * * 3"
  retry_attempts: 3
  retry_backoff_seconds: 5
  sap_api_base_url: ""
claude:
  default_model: "us.anthropic.claude-sonnet-4-6-20250514"
  complex_model: "us.anthropic.claude-opus-4-6-20250514"
  complex_threshold_cvss: 9.0
  max_tokens: 4096
azure:
  tenant_id: ""
  client_id: ""
  client_secret: ""
""")
    config = load_config(settings_yaml)
    assert isinstance(config, Settings)
    assert config.app.name == "Test App"
    assert config.app.mode == "local"
    assert config.database.path == "data/test.db"


def test_load_rules_returns_rules_config(tmp_path):
    rules_yaml = tmp_path / "rules.yaml"
    rules_yaml.write_text("""
version_matching:
  strategies:
    - exact_range
    - prefix_match
component_aliases:
  "BC-SRV-KRN": ["KERNEL"]
product_component_map:
  "ECC": ["SAP_BASIS", "KERNEL"]
tier_weights:
  Prod: 4
  QA: 2
confidence_weights:
  HIGH: 1.0
  MEDIUM: 0.7
""")
    rules = load_rules(rules_yaml)
    assert isinstance(rules, RulesConfig)
    assert "exact_range" in rules.version_matching.strategies
    assert rules.component_aliases["BC-SRV-KRN"] == ["KERNEL"]
    assert rules.tier_weights["Prod"] == 4


def test_load_component_map(tmp_path):
    map_yaml = tmp_path / "component_map.yaml"
    map_yaml.write_text("""
components:
  SAP_BASIS:
    description: "SAP Basis"
    aliases: ["SAPBASIS", "SAP BASIS"]
  KERNEL:
    description: "SAP Kernel"
    aliases: ["SAP_KERNEL"]
""")
    cmap = load_component_map(map_yaml)
    assert "SAP_BASIS" in cmap
    assert "SAPBASIS" in cmap["SAP_BASIS"]["aliases"]
