from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AppConfig:
    name: str
    mode: str
    secret_key: str
    debug: bool = False


@dataclass
class DatabaseConfig:
    path: str


@dataclass
class IngestionConfig:
    schedule_cron: str
    retry_attempts: int
    retry_backoff_seconds: int
    sap_api_base_url: str


@dataclass
class GateConfig:
    applicable_confidence_threshold: float = 0.85
    applicable_evidence_threshold: float = 0.90
    not_applicable_confidence_threshold: float = 0.95
    not_applicable_evidence_threshold: float = 0.95
    borderline_margin: float = 0.10
    enable_verification: bool = True


@dataclass
class ClaudeConfig:
    default_model: str
    complex_model: str
    complex_threshold_cvss: float
    max_tokens: int
    gate: GateConfig = field(default_factory=GateConfig)


@dataclass
class AzureConfig:
    tenant_id: str
    client_id: str
    client_secret: str


@dataclass
class Settings:
    app: AppConfig
    database: DatabaseConfig
    ingestion: IngestionConfig
    claude: ClaudeConfig
    azure: AzureConfig


@dataclass
class VersionMatching:
    strategies: list[str]


@dataclass
class RulesConfig:
    version_matching: VersionMatching
    component_aliases: dict[str, list[str]]
    product_component_map: dict[str, list[str]]
    tier_weights: dict[str, float]
    confidence_weights: dict[str, float]


def load_config(path: Path) -> Settings:
    with open(path) as f:
        data = yaml.safe_load(f)
    return Settings(
        app=AppConfig(**data["app"]),
        database=DatabaseConfig(**data["database"]),
        ingestion=IngestionConfig(**data["ingestion"]),
        claude=_parse_claude_config(data["claude"]),
        azure=AzureConfig(**data["azure"]),
    )


def _parse_claude_config(data: dict) -> ClaudeConfig:
    gate_data = data.pop("gate", {})
    gate = GateConfig(**gate_data) if gate_data else GateConfig()
    return ClaudeConfig(**data, gate=gate)


def load_rules(path: Path) -> RulesConfig:
    with open(path) as f:
        data = yaml.safe_load(f)
    return RulesConfig(
        version_matching=VersionMatching(**data["version_matching"]),
        component_aliases=data["component_aliases"],
        product_component_map=data["product_component_map"],
        tier_weights=data["tier_weights"],
        confidence_weights=data["confidence_weights"],
    )


def load_component_map(path: Path) -> dict[str, Any]:
    with open(path) as f:
        data = yaml.safe_load(f)
    return data["components"]
