"""Deterministic analysis of a single AI answer.

- entity mentions (alias matching with Unicode word boundaries)
- explicit ranking (numbered lists only)
- recommendation vs mention heuristic
- citation extraction + source classification

No LLM is used here: every number shown in the dashboard is reproducible.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .registry import Entity, Registry

URL_RE = re.compile(r"https?://[^\s<>\"'\)\]\}]+", re.IGNORECASE)
NUMBERED_RE = re.compile(r"^\s*(?:\*\*)?(\d{1,2})[\.\)]\s+(.+)$")
BULLET_RE = re.compile(r"^\s*[-*•]\s+(.+)$")

RECOMMEND_CUES = (
    "рекоменд", "совету", "советую", "лучш", "стоит обратить", "обратите внимание",
    "подойд", "хороший выбор", "надёжн", "надежн", "популярн", "топ",
    "recommend", "best", "top",
)
NEGATIVE_CUES = ("не рекоменд", "не стоит", "избегайте", "не советую", "not recommend", "avoid")

SOURCE_TYPES = {
    "map_directory": ("2gis.kz", "2gis.ru", "2gis.com", "go.2gis.com", "yandex.kz/maps", "yandex.ru/maps",
                      "maps.google", "maps.app.goo.gl", "google.com/maps"),
    "marketplace": ("kaspi.kz", "wildberries", "ozon.", "satu.kz", "market.kz", "olx.kz", "flip.kz", "halykmarket"),
    "social": ("instagram.com", "facebook.com", "youtube.com", "youtu.be", "tiktok.com", "t.me", "vk.com",
               "pinterest.", "dzen.ru"),
    "review_q&a": ("otzovik", "irecommend", "yell.kz", "flamp", "reddit.com", "otzyvy"),
    "encyclopedia": ("wikipedia.org",),
}


@dataclass
class Mention:
    entity_id: str
    level: str
    first_pos: int
    count: int
    recommended: bool
    rank: int | None  # position in an explicit numbered list, else None


@dataclass
class Citation:
    url: str
    domain: str
    source_type: str
    owner_entity: str | None


@dataclass
class AnswerAnalysis:
    mentions: dict[str, Mention] = field(default_factory=dict)
    citations: list[Citation] = field(default_factory=list)
    has_ranking: bool = False
    ranked_entities: list[str] = field(default_factory=list)


def normalize(text: str) -> str:
    return text.lower().replace("ё", "е")


def _alias_pattern(alias: str) -> re.Pattern:
    a = re.escape(normalize(alias)).replace(r"\ ", r"[\s\-]+")
    return re.compile(rf"(?<![\w.]){a}(?![\w])")


_PATTERN_CACHE: dict[str, list[re.Pattern]] = {}


def find_entity_spans(text: str, entity: Entity) -> list[int]:
    pats = _PATTERN_CACHE.get(entity.id)
    if pats is None:
        aliases = sorted(set(entity.aliases) | {entity.name} | set(entity.domains), key=len, reverse=True)
        pats = [_alias_pattern(a) for a in aliases if a]
        _PATTERN_CACHE[entity.id] = pats
    norm = normalize(text)
    hits: set[int] = set()
    covered: list[tuple[int, int]] = []
    for p in pats:  # longest alias first; skip overlaps so "Центр Красок №1" counts once
        for m in p.finditer(norm):
            if any(s <= m.start() < e for s, e in covered):
                continue
            covered.append((m.start(), m.end()))
            hits.add(m.start())
    return sorted(hits)


def normalize_domain(url: str) -> str:
    try:
        host = urlsplit(url).hostname or ""
    except ValueError:
        return ""
    host = host.lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def clean_url(url: str) -> str:
    return url.rstrip(".,;:!?»”")


def classify_source(url: str, registry: Registry) -> tuple[str, str | None]:
    domain = normalize_domain(url)
    owner = registry.entity_for_domain(domain)
    low = url.lower()
    for stype, needles in SOURCE_TYPES.items():
        if any(n in low for n in needles):
            return stype, owner.id if owner else None
    if owner is not None:
        if owner.level == "retailer":
            return ("client_site" if owner.is_client else "retailer_site"), owner.id
        return "manufacturer_site", owner.id
    return "other_web", None


def extract_citations(text: str, registry: Registry, extra_urls: list[str] | None = None) -> list[Citation]:
    seen: set[str] = set()
    out: list[Citation] = []
    for raw in list(URL_RE.findall(text)) + list(extra_urls or []):
        url = clean_url(raw.strip())
        key = url.split("#")[0].rstrip("/").lower()
        if not url or key in seen:
            continue
        seen.add(key)
        stype, owner = classify_source(url, registry)
        out.append(Citation(url=url, domain=normalize_domain(url), source_type=stype, owner_entity=owner))
    return out


def _sentence_around(text: str, pos: int) -> str:
    start = max(text.rfind(".", 0, pos), text.rfind("\n", 0, pos)) + 1
    ends = [i for i in (text.find(".", pos), text.find("\n", pos)) if i != -1]
    end = min(ends) if ends else len(text)
    return text[start:end]


def parse_ranking(text: str, registry: Registry, entities: list[Entity]) -> list[str]:
    """Entities in order of an explicit numbered list. Only the first entity per item counts."""
    ranked: list[str] = []
    for line in text.splitlines():
        m = NUMBERED_RE.match(line)
        if not m:
            continue
        item = m.group(2)
        best: tuple[int, str] | None = None
        for e in entities:
            spans = find_entity_spans(item, e)
            if spans and (best is None or spans[0] < best[0]):
                best = (spans[0], e.id)
        if best and best[1] not in ranked:
            ranked.append(best[1])
    return ranked


def analyze_answer(text: str, registry: Registry, cited_urls: list[str] | None = None) -> AnswerAnalysis:
    entities = list(registry.entities.values())
    res = AnswerAnalysis()
    numbered_lines = [ln for ln in text.splitlines() if NUMBERED_RE.match(ln)]
    res.has_ranking = len(numbered_lines) >= 2
    if res.has_ranking:
        res.ranked_entities = parse_ranking(text, registry, entities)
    list_lines = numbered_lines + [ln for ln in text.splitlines() if BULLET_RE.match(ln)]
    norm_text = normalize(text)
    for e in entities:
        spans = find_entity_spans(text, e)
        if not spans:
            continue
        recommended = False
        for pos in spans:
            sent = _sentence_around(norm_text, pos)
            if any(c in sent for c in NEGATIVE_CUES):
                continue
            in_list = any(find_entity_spans(ln, e) for ln in list_lines)
            if in_list or any(c in sent for c in RECOMMEND_CUES):
                recommended = True
                break
        rank = res.ranked_entities.index(e.id) + 1 if e.id in res.ranked_entities else None
        res.mentions[e.id] = Mention(e.id, e.level, spans[0], len(spans), recommended, rank)
    res.citations = extract_citations(text, registry, cited_urls)
    return res
