from dataclasses import dataclass, field
from collections import defaultdict
from src.landscape.normalizer import NormalizedEntry


@dataclass
class SystemMatch:
    sid: str
    component_code: str
    version: str
    version_numeric: int
    sp_level: int
    tier: str
    product: str
    description: str


@dataclass
class ComponentIndex:
    components: dict[str, dict[int, list[SystemMatch]]] = field(default_factory=dict)

    def lookup(
        self, component: str, min_version: int, max_version: int
    ) -> list[SystemMatch]:
        if component not in self.components:
            return []
        matches = []
        for version, systems in self.components[component].items():
            if min_version <= version <= max_version:
                matches.extend(systems)
        return matches


def build_component_index(entries: list[NormalizedEntry]) -> ComponentIndex:
    components: dict[str, dict[int, list[SystemMatch]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for entry in entries:
        if not entry.component_code or entry.version_numeric == 0:
            continue
        sp = 0
        if entry.notes and entry.notes.startswith("SP:"):
            try:
                sp = int(entry.notes.replace("SP:", "").strip())
            except ValueError:
                pass
        system_match = SystemMatch(
            sid=entry.sid,
            component_code=entry.component_code,
            version=entry.version,
            version_numeric=entry.version_numeric,
            sp_level=sp,
            tier=entry.tier,
            product=entry.product,
            description=entry.description,
        )
        components[entry.component_code][entry.version_numeric].append(system_match)
    return ComponentIndex(components=dict(components))
