from src.ingestion.parser import ParsedNote, VersionRange
from src.landscape.indexer import ComponentIndex
from src.matching.models import MatchEntry
from src.shared.config import RulesConfig


class RulesEngine:
    def __init__(self, config: RulesConfig):
        self.config = config

    def match(self, note: ParsedNote, index: ComponentIndex) -> list[MatchEntry]:
        matches = []
        seen = set()

        for vr in note.version_ranges:
            # Only match if we have SP-level data (fix_sp > 0)
            if not vr.fix_sp:
                continue
            resolved_components = self._resolve_component(vr.component)
            for component in resolved_components:
                systems = index.lookup(component, min_version=vr.min, max_version=vr.max)
                for system in systems:
                    key = (note.note_number, system.sid, component)
                    if key in seen:
                        continue
                    # System is affected only if its SP level is BELOW the fix SP
                    if system.sp_level >= vr.fix_sp:
                        continue
                    seen.add(key)
                    entry = MatchEntry(
                        note_number=note.note_number,
                        sid=system.sid,
                        component=component,
                        system_version=system.version,
                        affected_range=f"{vr.min}-{vr.max}",
                        tier=system.tier,
                        confidence="HIGH",
                        match_source="rules_engine",
                        match_reason=(
                            f"{component} v{system.version} SP{system.sp_level} "
                            f"below fix level SP{vr.fix_sp}"
                        ),
                    )
                    matches.append(entry)

        return matches

    def _resolve_component(self, component: str) -> list[str]:
        aliases = self.config.component_aliases
        if component in aliases:
            return aliases[component]
        for canonical, alias_list in aliases.items():
            if component in alias_list:
                return [component]
        return [component]
