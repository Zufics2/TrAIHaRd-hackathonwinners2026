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
    "подойд", "хороший выбор", "надёжн", "надежн", "популярн", "топ", "первый выбор", "в первую очередь",
    "recommend", "best", "top",
)
NEGATIVE_CUES = ("не рекоменд", "не стоит", "избегайте", "не советую", "не продает", "не продают", "нет в ассортименте",
                 "не специализир", "не подойдет", "not recommend", "avoid", "ұсынбаймын")

# Each needle is "host-suffix" or "host-suffix/path-prefix"; matched against the parsed host and path only,
# never against the query string (https://evil.example/?next=https://2gis.kz/ is NOT a map directory).
SOURCE_TYPES = {
    "map_directory": ("2gis.kz", "2gis.ru", "2gis.com", "yandex.kz/maps", "yandex.ru/maps", "yandex.com/maps",
                      "maps.google.com", "maps.app.goo.gl", "google.com/maps", "google.kz/maps", "goo.gl/maps",
                      "jsprav.ru", "zoon.kz", "zoon.ru", "spr.kz"),  # business directories (address / phone cards)
    "marketplace": ("kaspi.kz", "wildberries.ru", "wildberries.kz", "wb.ru", "ozon.ru", "ozon.kz", "satu.kz", "market.kz",
                    "olx.kz", "flip.kz", "halykmarket.kz", "e-katalog.kz"),
    "social": ("instagram.com", "facebook.com", "youtube.com", "youtu.be", "tiktok.com", "t.me", "vk.com",
               "pinterest.com", "dzen.ru", "threads.net"),
    "review_q&a": ("otzovik.com", "irecommend.ru", "yell.kz", "flamp.kz", "flamp.ru", "reddit.com"),
    "encyclopedia": ("wikipedia.org",),
}


def _host_path(url: str) -> tuple[str, str]:
    try:
        p = urlsplit(url)
        host = (p.hostname or "").lower().rstrip(".")
    except ValueError:
        return "", ""
    return (host[4:] if host.startswith("www.") else host), (p.path or "/").lower()


def _needle_match(host: str, path: str, needle: str) -> bool:
    nh, _, np_ = needle.partition("/")
    if not (host == nh or host.endswith("." + nh)):
        return False
    return not np_ or path.startswith("/" + np_)


def is_web_url(url: str) -> bool:
    """Absolute http(s) URL with a host. Rejects javascript:, data:, relative paths (QA-004)."""
    try:
        p = urlsplit(url.strip())
    except ValueError:
        return False
    return p.scheme in ("http", "https") and bool(p.hostname)


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


CYR_WORD = re.compile(r"^[а-я]+$")
CYR_VOWEL_END = re.compile(r"[аеиоуыэюяй]$")


def _alias_pattern(alias: str, keep_case: bool = False) -> re.Pattern:
    """Exact match for single-word aliases. In multi-word Cyrillic aliases each word may take a
    Russian case ending ("Центр Красок" -> "Центре Красок", "Центра Красок")."""
    words = (alias.replace("ё", "е") if keep_case else normalize(alias)).split()
    parts = []
    for w in words:
        if len(words) > 1 and CYR_WORD.match(w.lower()) and len(w) >= 4:
            stem = CYR_VOWEL_END.sub("", w)
            parts.append(re.escape(stem) + r"[а-я]{0,3}")
        else:
            parts.append(re.escape(w))
    a = r"[\s\-]+".join(parts)
    return re.compile(rf"(?<![\w.]){a}(?![\w])")


# Keyed by everything that defines the patterns, so a registry edit with the same id never reuses stale
# patterns (QA-006).
_PATTERN_CACHE: dict[tuple, list[re.Pattern]] = {}


def _cs_pattern(alias: str) -> re.Pattern:
    a = re.escape(alias.replace("ё", "е")).replace(r"\ ", r"[\s\-]+")
    return re.compile(rf"(?<![\w.]){a}(?![\w])")


def _patterns(entity: Entity) -> list[tuple[re.Pattern, bool]]:
    key = (entity.id, entity.name, entity.aliases, entity.domains, entity.case_sensitive, entity.case_sensitive_aliases)  # exclude_preceding: applied in find_entity_spans
    pats = _PATTERN_CACHE.get(key)
    if pats is None:
        aliases = sorted(set(entity.aliases) | {entity.name} | set(entity.domains), key=len, reverse=True)
        # Brands that are also common words ("favourite") match only in their written case (QA-009);
        # domains are always case-insensitive.
        pats = [(_cs_pattern(a), True) if entity.case_sensitive and a not in entity.domains else (_alias_pattern(a), False)
                for a in aliases if a]
        # proper-name forms matched in their written case, Russian endings allowed ("в Центре Красок", not "центры красок")
        pats += [(_alias_pattern(a, keep_case=True), True) for a in sorted(entity.case_sensitive_aliases, key=len, reverse=True)]
        _PATTERN_CACHE[key] = pats
    return pats


def find_entity_spans(text: str, entity: Entity) -> list[int]:
    pats = _patterns(entity)
    norm = normalize(text)
    raw = text.replace("ё", "е")  # same length as norm, positions align
    hits: set[int] = set()
    covered: list[tuple[int, int]] = []
    excl = {normalize(w) for w in entity.exclude_preceding}
    for p, cs in pats:  # longest alias first; skip overlaps so "Центр Красок №1" counts once
        for m in p.finditer(raw if cs else norm):
            if any(s <= m.start() < e for s, e in covered):
                continue
            prev = re.findall(r"\w+", norm[max(0, m.start() - 40):m.start()])
            if excl and prev and prev[-1] in excl:
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
    return url.rstrip(".,;:!?»”*`")


TRACKING_PARAM = re.compile(r"^(utm_[a-z]+|gclid|fbclid|yclid|srsltid)=", re.IGNORECASE)


def url_key(url: str) -> str:
    """Dedup key: drop fragment, tracking params (ChatGPT adds ?utm_source=chatgpt.com), www, trailing slash."""
    try:
        p = urlsplit(url)
    except ValueError:
        return url.lower()
    query = "&".join(q for q in p.query.split("&") if q and not TRACKING_PARAM.match(q))
    host = (p.hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    return f"{host}{p.path.rstrip('/')}" + (f"?{query}" if query else "")


def classify_source(url: str, registry: Registry) -> tuple[str, str | None]:
    domain = normalize_domain(url)
    owner = registry.entity_for_domain(domain)
    host, path = _host_path(url)
    for stype, needles in SOURCE_TYPES.items():
        if any(_needle_match(host, path, n) for n in needles):
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
        if not is_web_url(url):
            continue
        key = url_key(url)
        if key in seen:
            continue
        seen.add(key)
        stype, owner = classify_source(url, registry)
        out.append(Citation(url=url, domain=normalize_domain(url), source_type=stype, owner_entity=owner))
    return out


SENT_BOUNDARY = re.compile(r"[.!?…](?=\s|$)|\n")
# Words that introduce a list of suggestions (in addition to RECOMMEND_CUES).
LIST_INTRO_CUES = ("вариант", "можно купить", "купить можно", "где купить", "стоит рассмотреть", "рассмотрите",
                   "подойдут", "подходят", "советую", "посмотрите", "обратите внимание", "стоит посетить", "в следующих", "options", "consider")
MARKUP_LEAD = re.compile(r"^[\s*_#>\[\]`\"'«“(]+")


def _sentence_around(text: str, pos: int) -> str:
    """Sentence containing pos. A dot inside a token (svet.kz) is not a boundary."""
    start = 0
    for m in SENT_BOUNDARY.finditer(text, 0, pos):
        start = m.end()
    m = SENT_BOUNDARY.search(text, pos)
    return text[start:m.start() if m else len(text)]


def _head_entity(item: str, entities: list[Entity]) -> str | None:
    """Entity that the list item is ABOUT: it must open the item (at most one word before it, e.g.
    "Магазин SVET.KZ"). "Откройте сайт Dulux" is an instruction, not an item about Dulux (QA-001)."""
    best: tuple[int, str] | None = None
    for e in entities:
        spans = find_entity_spans(item, e)
        if not spans:
            continue
        prefix = MARKUP_LEAD.sub("", item[:spans[0]])
        words = re.findall(r"\w+", prefix)
        if words and IMPERATIVE_RE.search(words[0].lower()):  # "Проверьте Dulux" is an instruction (G09)
            continue
        if len(words) <= 1 and (best is None or spans[0] < best[0]):
            best = (spans[0], e.id)
    return best[1] if best else None


IMPERATIVE_RE = re.compile(r"(?:ите|йте|ьте|ете)$")  # Russian plural imperative: проверьте, откройте, посмотрите
SOURCE_LINE_RE = re.compile(r"^[ \t]*(?:источники?|ссылки|sources?)[ \t]*:.*$", re.I | re.M)
SOURCE_CHIP_RE = re.compile(r"\b[\w-]+(?:\.[\w-]+)+\+\d+\b")  # ChatGPT source chips: "svet.kz+1"
CLAUSE_BOUNDARY = re.compile(r"[,;:—–]|\s(?:но|а|однако)\s")


def mask_sources(text: str) -> str:
    """Answer text with URLs, source chips and 'Источники:' lines blanked (same length, positions kept).
    A store that appears ONLY as a link is cited, not mentioned in the answer (G10)."""
    def blank(m: re.Match) -> str:
        return " " * len(m.group(0))
    for rx in (URL_RE, SOURCE_CHIP_RE, SOURCE_LINE_RE):
        text = rx.sub(blank, text)
    return text


def _clause_around(text: str, pos: int) -> tuple[str, str]:
    """(clause, part of the clause before pos) inside the sentence containing pos."""
    sent_start = 0
    for m in SENT_BOUNDARY.finditer(text, 0, pos):
        sent_start = m.end()
    start = sent_start
    for m in CLAUSE_BOUNDARY.finditer(text, sent_start, pos):
        start = m.end()
    m = CLAUSE_BOUNDARY.search(text, pos)
    s = SENT_BOUNDARY.search(text, pos)
    end = min(x.start() for x in (m, s) if x) if (m or s) else len(text)
    return text[start:end], text[start:pos]


def _intro(lines: list[str]) -> str:
    """Introduction of a list = the last line ending with ':' among the 3 lines before it, else those
    3 lines. Real ChatGPT answers put a heading and an image caption between the intro and item 1."""
    tail = lines[-3:]
    for ln in reversed(tail):
        if ln.rstrip().endswith(":"):
            return ln
    return "\n".join(tail)


def _list_items(text: str) -> list[dict]:
    """Numbered/bulleted items with the text that introduces their list. Items "2.", "3." … of a
    numbered list keep the intro of item "1." even when detail lines sit between them."""
    items, recent, intro, list_intro, last_num = [], [], "", "", None
    for line in text.splitlines():
        num = NUMBERED_RE.match(line)
        m = num or BULLET_RE.match(line)
        if m:
            if recent:
                intro, recent = _intro(recent), []
            item_intro = intro
            if num:
                n = int(num.group(1))
                if last_num is not None and n == last_num + 1:
                    item_intro = list_intro
                else:
                    list_intro = intro
                last_num = n
            items.append({"text": m.groups()[-1], "numbered": bool(num), "intro": item_intro,
                          "num": int(num.group(1)) if num else None})
        elif line.strip():
            recent.append(line)
    return items


def parse_ranking(text: str, registry: Registry, entities: list[Entity]) -> list[str]:
    """Entities heading the items of an explicit numbered list, in list order."""
    ranked: list[str] = []
    for it in _list_items(text):
        if it["numbered"]:
            head = _head_entity(it["text"], entities)
            if head and head not in ranked:
                ranked.append(head)
    return ranked


def _has(text: str, cues) -> bool:
    t = normalize(text)
    return any(c in t for c in cues)


def analyze_answer(text: str, registry: Registry, cited_urls: list[str] | None = None) -> AnswerAnalysis:
    """Mentions are searched in the answer text WITHOUT links (G10).
    Ranking: >=2 numbered items headed by an entity, in a list introduced as options/recommendations
    (or with no intro); a neutral catalogue ("Каталог производителей:") is not a ranking (G09).
    Rank = the item's own number, so unknown stores do not compress positions (G08).
    Recommendation (heuristic): heads an item of an options list / explicit ranking, OR a positive cue
    in the sentence that is not part of a negation and no negation in the entity's own clause (G09)."""
    entities = list(registry.entities.values())
    res = AnswerAnalysis()
    body = mask_sources(text)
    items = _list_items(body)
    for it in items:
        it["head"] = _head_entity(it["text"], entities)
        it["rank_list"] = it["numbered"] and not _has(it["intro"], NEGATIVE_CUES) and (
            not it["intro"].strip() or _has(it["intro"], RECOMMEND_CUES + LIST_INTRO_CUES))
    ranked = [(it["num"], it["head"]) for it in items if it["rank_list"] and it["head"]]
    res.has_ranking = len(ranked) >= 2
    first_rank: dict[str, int] = {}
    if res.has_ranking:
        for num, head in ranked:
            first_rank.setdefault(head, num)
        res.ranked_entities = list(first_rank)
    norm_text = normalize(body)
    for e in entities:
        spans = find_entity_spans(body, e)
        if not spans:
            continue
        recommended = False
        for it in items:
            if it["head"] != e.id or _has(it["text"], NEGATIVE_CUES):
                continue
            intro_ok = _has(it["intro"], RECOMMEND_CUES + LIST_INTRO_CUES) and not _has(it["intro"], NEGATIVE_CUES)
            if intro_ok or (it["rank_list"] and res.has_ranking and not it["intro"].strip()):
                recommended = True
                break
        if not recommended:
            for pos in spans:
                sent = _sentence_around(norm_text, pos)
                positive = sent
                for c in NEGATIVE_CUES:
                    positive = positive.replace(c, " ")
                clause, before = _clause_around(norm_text, pos)
                negated = any(c in clause for c in NEGATIVE_CUES) or re.search(r"(?:^|\s)(?:не|кроме)\s+(?:\S+\s+)?$", before)
                if not negated and any(c in positive for c in RECOMMEND_CUES):
                    recommended = True
                    break
        rank = first_rank.get(e.id)
        res.mentions[e.id] = Mention(e.id, e.level, spans[0], len(spans), recommended, rank)
    res.citations = extract_citations(text, registry, cited_urls)
    return res
