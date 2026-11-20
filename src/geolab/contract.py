"""Data contract: allowed values + row-level validator for every exchange file.

CLI:
    python -m geolab.contract observations data/raw/manual/P3_observations_chatgpt.csv
    python -m geolab.contract prompts|brand_catalog|sources|proposals <file>

Exit code 0 = no errors (warnings allowed), 1 = errors found.
Row numbers: CSV — line in the file (header = 1, first data row = 2); JSONL — line number.
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

# ---------------- allowed values (single source of truth) ----------------
CATEGORY = ("paint", "chandelier")
CITY = ("almaty", "astana", "karaganda", "national")
FUNNEL_STAGE = ("brand_discovery", "retailer_discovery", "bridge")
INTENT = ("informational", "problem-aware", "category-aware", "brand-aware", "comparison",
          "transactional", "local", "post-purchase")
BRAND_TYPE = ("unbranded", "branded", "competitor-branded")
TEST_GROUP = ("retail", "brand", "bridge", "branded")
LANGUAGE = ("ru", "kk", "en")
PRIORITY = ("P0", "P1", "P2")
PROVIDER = ("chatgpt_search", "gemini", "perplexity", "google_ai_mode", "google_ai_overview",
            "copilot", "yandex_alice", "other")
SEARCH_MODE = ("search_on", "unknown")  # search_off answers are NOT AI-search observations
DATA_TYPE = ("REAL_SEARCH", "MANUAL_VERIFIED", "CONTROLLED_EXPERIMENT", "SYNTHETIC_DEMO")
REAL_DATA_TYPES = ("REAL_SEARCH", "MANUAL_VERIFIED")
VERIFICATION = ("pending", "verified", "rejected")
ENTITY_LEVEL = ("manufacturer", "retailer")
SOURCE_TYPE = ("client_site", "retailer_site", "manufacturer_site", "map_directory", "marketplace",
               "social", "review_q&a", "media", "encyclopedia", "other_web")
IMPLEMENTATION_TYPE = ("SITE_CONTENT", "PRODUCT_CARD", "BRAND_PAGE", "RETAILER_PAGE", "CATEGORY_PAGE",
                       "STRUCTURED_DATA", "INTERNAL_LINK", "LOCAL_BUSINESS_PROFILE", "PRODUCT_CATALOG",
                       "VERIFIED_THIRD_PARTY_MENTION", "SOCIAL_CONTENT", "VERIFIED_REVIEW_RESPONSE")
CONFIDENCE = ("low", "medium", "high")

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{1,63}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_]{1,63}$")
EARLIEST = datetime(2026, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class Col:
    name: str
    kind: str = "text"  # text | id | slug | enum | url | urls | datetime | int | list
    required: bool = True
    allowed: tuple = ()


SCHEMAS: dict[str, dict] = {
    "observations": {
        "key": "response_id",
        "cols": (
            Col("response_id", "id"), Col("prompt_id", "id"), Col("query"),
            Col("provider", "enum", allowed=PROVIDER), Col("model", required=False),
            Col("search_mode", "enum", allowed=SEARCH_MODE), Col("timestamp", "datetime"),
            Col("run_no", "int"), Col("language", "enum", allowed=LANGUAGE),
            Col("region_setting", required=False), Col("answer_text"), Col("cited_urls", "urls", required=False),
            Col("data_type", "enum", allowed=DATA_TYPE), Col("verification_status", "enum", allowed=VERIFICATION),
            Col("collector", "id"), Col("verified_by", required=False), Col("evidence_link", required=False),
            Col("notes", required=False),
        ),
    },
    "prompts": {
        "key": "prompt_id",
        "cols": (
            Col("prompt_id", "id"), Col("query"), Col("category", "enum", allowed=CATEGORY),
            Col("city", "enum", allowed=CITY), Col("language", "enum", allowed=LANGUAGE),
            Col("funnel_stage", "enum", allowed=FUNNEL_STAGE), Col("intent", "enum", allowed=INTENT),
            Col("brand_type", "enum", allowed=BRAND_TYPE), Col("test_group", "enum", allowed=TEST_GROUP),
            Col("priority", "enum", allowed=PRIORITY), Col("notes", required=False),
        ),
    },
    "brand_catalog": {
        "key": "catalog_id",
        "cols": (
            Col("catalog_id", "id"), Col("manufacturer_id", "slug"), Col("manufacturer_name"),
            Col("category", "enum", allowed=CATEGORY), Col("retailer_id", "slug"),
            Col("product_name", required=False), Col("sku", required=False),
            Col("evidence_url", "url"), Col("observed_at", "datetime"), Col("availability_note", required=False),
            Col("verification_status", "enum", allowed=VERIFICATION), Col("collector", "id"), Col("notes", required=False),
        ),
    },
    "sources": {
        "key": "source_id",
        "cols": (
            Col("source_id", "id"), Col("entity_id", "slug"), Col("entity_level", "enum", allowed=ENTITY_LEVEL),
            Col("url", "url"), Col("source_type", "enum", allowed=SOURCE_TYPE), Col("platform", required=False),
            Col("city", "enum", allowed=CITY), Col("ownership", "enum", allowed=("owned", "third_party", "unknown")),
            Col("content_summary"), Col("issues_found", required=False),
            Col("cited_in_response_ids", "list", required=False), Col("observed_at", "datetime"),
            Col("verification_status", "enum", allowed=VERIFICATION), Col("collector", "id"),
        ),
    },
    "proposals": {
        "key": "issue_id",
        "cols": (
            Col("issue_id", "id"), Col("affected_entity", "slug"), Col("source_url", "url"), Col("finding"),
            Col("evidence"), Col("implementation_type", "enum", allowed=IMPLEMENTATION_TYPE),
            Col("before", required=False), Col("after"), Col("why"),
            Col("priority", "enum", allowed=PRIORITY), Col("cost", "enum", allowed=CONFIDENCE),
            Col("expected_mechanism"), Col("confidence", "enum", allowed=CONFIDENCE),
            Col("experiment_plan"), Col("collector", "id"),
        ),
    },
}


@dataclass
class Issue:
    row: int
    field: str
    severity: str  # error | warning
    reason: str

    def as_dict(self) -> dict:
        return {"row": self.row, "field": self.field, "severity": self.severity, "reason": self.reason}


def _is_url(v: str) -> bool:
    try:
        p = urlsplit(v)
    except ValueError:
        return False
    return p.scheme in ("http", "https") and bool(p.netloc) and " " not in v


def split_urls(v: str) -> list[str]:
    return [u for u in re.split(r"[\s|]+", v or "") if u]


def parse_dt(v: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(v.strip())
    except ValueError:
        return None
    return dt if dt.tzinfo else None


def _check_cell(col: Col, v: str, row: int, now: datetime) -> list[Issue]:
    if v == "":
        return [Issue(row, col.name, "error", "обязательное поле пустое")] if col.required else []
    k = col.kind
    if k == "id" and not ID_RE.match(v):
        return [Issue(row, col.name, "error", f"недопустимый ID {v!r}: латиница/цифры/_/-, 2–64 символа")]
    if k == "slug" and not SLUG_RE.match(v):
        return [Issue(row, col.name, "error", f"недопустимый slug {v!r}: a-z, 0-9, _")]
    if k == "enum" and v not in col.allowed:
        return [Issue(row, col.name, "error", f"значение {v!r} не из списка {list(col.allowed)}")]
    if k == "url" and not _is_url(v):
        return [Issue(row, col.name, "error", f"не URL: {v!r}")]
    if k == "urls":
        return [Issue(row, col.name, "error", f"не URL: {u!r} (разделяйте ссылки ' | ')") for u in split_urls(v) if not _is_url(u)]
    if k == "int" and (not v.isdigit() or int(v) < 1):
        return [Issue(row, col.name, "error", f"нужно целое ≥ 1, получено {v!r}")]
    if k == "datetime":
        dt = parse_dt(v)
        if dt is None:
            return [Issue(row, col.name, "error", f"дата {v!r} не в формате ISO 8601 с часовым поясом, пример 2026-11-20T15:04+05:00")]
        if dt > now + timedelta(minutes=10):
            return [Issue(row, col.name, "error", f"дата {v} в будущем")]
        if dt < EARLIEST:
            return [Issue(row, col.name, "error", f"дата {v} раньше 2026-01-01")]
    return []


def _norm_q(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower().replace("ё", "е"))


def validate_rows(kind: str, rows: list[tuple[int, dict]], *, prompts: dict[str, dict] | None = None,
                  known_entities: set[str] | None = None, allow_synthetic: bool = False,
                  existing_keys: set[str] | None = None, now: datetime | None = None) -> tuple[list[dict], list[Issue]]:
    """rows = [(row_number, dict)]. Returns (valid_rows, issues). A row with any error is not returned."""
    schema = SCHEMAS[kind]
    now = now or datetime.now(timezone.utc)
    issues: list[Issue] = []
    valid: list[dict] = []
    seen: dict[str, int] = {}
    if rows:
        header = set(rows[0][1].keys())
        missing = [c.name for c in schema["cols"] if c.name not in header]
        unknown = sorted(h for h in header if h not in {c.name for c in schema["cols"]} and h is not None)
        if missing:
            return [], [Issue(1, ",".join(missing), "error", "в заголовке нет обязательных столбцов")]
        if unknown:
            issues.append(Issue(1, ",".join(unknown), "warning", "лишние столбцы будут проигнорированы"))
    for rn, raw in rows:
        if None in raw:
            issues.append(Issue(rn, "*", "error", "в строке больше значений, чем столбцов (лишняя запятая? заключите текст в кавычки)"))
            continue
        rec = {c.name: (raw.get(c.name) or "").strip() for c in schema["cols"]}
        row_issues: list[Issue] = []
        for c in schema["cols"]:
            row_issues += _check_cell(c, rec[c.name], rn, now)
        key = rec[schema["key"]]
        if key:
            if key in seen:
                row_issues.append(Issue(rn, schema["key"], "error", f"дубликат ID, уже в строке {seen[key]}"))
            elif existing_keys and key in existing_keys:
                row_issues.append(Issue(rn, schema["key"], "error", "ID уже существует в загруженных данных"))
            seen.setdefault(key, rn)
        if kind == "observations":
            row_issues += _observation_rules(rec, rn, prompts, allow_synthetic)
        if kind in ("brand_catalog", "sources", "proposals") and known_entities is not None:
            fld = {"brand_catalog": "retailer_id", "sources": "entity_id", "proposals": "affected_entity"}[kind]
            if rec[fld] and rec[fld] not in known_entities:
                sev = "warning" if kind != "brand_catalog" else "error"
                row_issues.append(Issue(rn, fld, sev, f"{rec[fld]!r} нет в data/registry/entities.json"))
        if kind == "brand_catalog" and known_entities is not None and rec["manufacturer_id"] not in known_entities:
            row_issues.append(Issue(rn, "manufacturer_id", "warning", "новый производитель — добавьте в реестр после проверки"))
        issues += row_issues
        if not any(i.severity == "error" for i in row_issues):
            if kind == "observations":
                rec["cited_urls"] = split_urls(rec["cited_urls"])
                rec["run_no"] = int(rec["run_no"])
            valid.append(rec)
    return valid, issues


def _observation_rules(rec: dict, rn: int, prompts: dict | None, allow_synthetic: bool) -> list[Issue]:
    out: list[Issue] = []
    dt = rec["data_type"]
    if dt == "CONTROLLED_EXPERIMENT":
        out.append(Issue(rn, "data_type", "error", "результаты эксперимента создаёт experiment engine, их нельзя импортировать как наблюдения"))
    if dt == "SYNTHETIC_DEMO" and not allow_synthetic:
        out.append(Issue(rn, "data_type", "error", "SYNTHETIC_DEMO нельзя импортировать в реальные данные (только data/samples/)"))
    if dt in REAL_DATA_TYPES and 0 < len(rec["answer_text"]) < 40:
        out.append(Issue(rn, "answer_text", "warning", "очень короткий ответ — вставлен ли полный текст?"))
    if dt == "MANUAL_VERIFIED" and not rec["evidence_link"]:
        out.append(Issue(rn, "evidence_link", "error", "для MANUAL_VERIFIED нужен скриншот или ссылка на диалог"))
    if rec["verification_status"] == "verified":
        if not rec["verified_by"]:
            out.append(Issue(rn, "verified_by", "error", "статус verified требует verified_by"))
        elif rec["verified_by"] == rec["collector"]:
            out.append(Issue(rn, "verified_by", "warning", "проверял тот же человек, что собирал"))
    if prompts is not None and rec["prompt_id"]:
        p = prompts.get(rec["prompt_id"])
        if p is None:
            out.append(Issue(rn, "prompt_id", "error", f"{rec['prompt_id']!r} нет в data/prompts/prompts.csv"))
        elif rec["query"] and _norm_q(p["query"]) != _norm_q(rec["query"]):
            out.append(Issue(rn, "query", "error", f"запрос отличается от prompts.csv: ожидалось {p['query']!r}"))
    return out


# ---------------- file readers ----------------
def read_rows(name: str, content: bytes) -> tuple[list[tuple[int, dict]], list[Issue]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], [Issue(0, "*", "error", "файл не в кодировке UTF-8 (в Excel: «Сохранить как → CSV UTF-8»)")]
    if name.endswith(".jsonl"):
        rows, issues = [], []
        for i, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                issues.append(Issue(i, "*", "error", f"невалидный JSON: {exc.msg}"))
                continue
            if isinstance(obj.get("cited_urls"), list):
                obj["cited_urls"] = " | ".join(obj["cited_urls"])
            rows.append((i, {k: "" if v is None else str(v) for k, v in obj.items()}))
        return rows, issues
    if name.endswith(".csv"):
        reader = csv.DictReader(io.StringIO(text, newline=""))
        rows, prev = [], 1
        for rec in reader:
            rows.append((prev + 1, rec))  # physical line where the record starts (multi-line answers OK)
            prev = reader.line_num
        if reader.fieldnames is None:
            return [], [Issue(1, "*", "error", "пустой файл")]
        return rows, []
    return [], [Issue(0, "*", "error", "поддерживаются только .csv и .jsonl")]


def validate_file(kind: str, path: Path, **kw) -> tuple[list[dict], list[Issue]]:
    path = Path(path)
    rows, issues = read_rows(path.name, path.read_bytes())
    valid, more = validate_rows(kind, rows, **kw)
    return valid, issues + more


def _context() -> dict:
    from .registry import load_registry
    from .store import load_prompts
    reg = load_registry()
    return {"prompts": {r["prompt_id"]: r for r in load_prompts().to_dict("records")},
            "known_entities": set(reg.entities)}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in SCHEMAS:
        print(f"usage: python -m geolab.contract {{{'|'.join(SCHEMAS)}}} <file>")
        return 2
    kind, path = argv
    ctx = _context()
    kw = {"prompts": ctx["prompts"]} if kind == "observations" else {}
    if kind in ("brand_catalog", "sources", "proposals"):
        kw["known_entities"] = ctx["known_entities"]
    kw["allow_synthetic"] = "samples" in Path(path).parts
    valid, issues = validate_file(kind, Path(path), **kw)
    for i in issues:
        print(f"{i.severity.upper():7} строка {i.row:>4} · {i.field}: {i.reason}")
    n_err = sum(i.severity == "error" for i in issues)
    print(f"\n{kind}: валидных строк {len(valid)}, ошибок {n_err}, предупреждений {len(issues) - n_err}")
    return 1 if n_err else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
