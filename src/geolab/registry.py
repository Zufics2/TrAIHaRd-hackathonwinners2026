"""Brand / Manufacturer / Retailer / City registry (LEVEL 1 and LEVEL 2 entities)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "data" / "registry" / "entities.json"


@dataclass(frozen=True)
class Entity:
    id: str
    name: str
    level: str  # "manufacturer" | "retailer"
    category: str
    aliases: tuple[str, ...]
    domains: tuple[str, ...] = ()
    is_client: bool = False
    status: str = "observed"
    sold_by: dict = field(default_factory=dict, hash=False, compare=False)
    cities: dict = field(default_factory=dict, hash=False, compare=False)


@dataclass
class Registry:
    entities: dict[str, Entity]
    cities: dict[str, dict]

    def by_level(self, level: str) -> list[Entity]:
        return [e for e in self.entities.values() if e.level == level]

    def clients(self) -> list[Entity]:
        return [e for e in self.entities.values() if e.is_client]

    def assortment(self, retailer_id: str) -> list[Entity]:
        """Manufacturers with an observed link to the retailer's catalog."""
        return [e for e in self.by_level("manufacturer") if retailer_id in e.sold_by]

    def entity_for_domain(self, domain: str) -> Entity | None:
        for e in self.entities.values():
            for d in e.domains:
                if domain == d or domain.endswith("." + d):
                    return e
        return None


def load_registry(path: Path = REGISTRY_PATH) -> Registry:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    ents: dict[str, Entity] = {}
    for r in raw.get("retailers", []):
        ents[r["id"]] = Entity(
            id=r["id"], name=r["name"], level="retailer", category=r.get("category", ""),
            aliases=tuple(r.get("aliases", [])), domains=tuple(r.get("domains", [])),
            is_client=bool(r.get("is_client")), status=r.get("status", "observed"),
            cities=r.get("cities", {}),
        )
    for m in raw.get("manufacturers", []):
        if m["id"] in ents:
            raise ValueError(f"duplicate entity id {m['id']}")
        ents[m["id"]] = Entity(
            id=m["id"], name=m["name"], level="manufacturer", category=m.get("category", ""),
            aliases=tuple(m.get("aliases", [])), domains=tuple(m.get("domains", [])),
            status=m.get("status", "observed"), sold_by=m.get("sold_by", {}),
        )
    return Registry(entities=ents, cities=raw.get("cities", {}))
