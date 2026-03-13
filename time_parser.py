from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

ROME_TZ = ZoneInfo("Europe/Rome")

ITALIAN_MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}

WEEKDAYS = {
    "lunedi": 0,
    "lunedì": 0,
    "martedi": 1,
    "martedì": 1,
    "mercoledi": 2,
    "mercoledì": 2,
    "giovedi": 3,
    "giovedì": 3,
    "venerdi": 4,
    "venerdì": 4,
    "sabato": 5,
    "domenica": 6,
}

NUMBER_WORDS = {
    "uno": 1,
    "una": 1,
    "due": 2,
    "tre": 3,
    "quattro": 4,
    "cinque": 5,
}

ORDINALS = {
    "primo": 1,
    "prima": 1,
    "secondo": 2,
    "seconda": 2,
    "terzo": 3,
    "terza": 3,
    "quarto": 4,
    "quarta": 4,
    "quinto": 5,
    "quinta": 5,
    "sesto": 6,
    "sesta": 6,
    "settimo": 7,
    "settima": 7,
    "ottavo": 8,
    "ottava": 8,
    "nono": 9,
    "nona": 9,
    "decimo": 10,
    "decima": 10,
}

CONFIRM_WORDS = {
    "conferma",
    "confermo",
    "ok",
    "va bene",
    "procedi",
    "si",
    "sì",
    "yes",
}
CANCEL_WORDS = {
    "annulla",
    "stop",
    "cancel",
    "cancella",
    "non confermo",
    "lascia stare",
}


def now_rome() -> datetime:
    return datetime.now(ROME_TZ).astimezone(ROME_TZ)


def _normalize_text(text: str) -> str:
    raw = (text or "").strip().lower()
    if not raw:
        return ""

    raw = " ".join(raw.split())
    normalized = "".join(
        ch
        for ch in unicodedata.normalize("NFD", raw)
        if unicodedata.category(ch) != "Mn"
    )
    return normalized


def extract_confirmation(text: str) -> str | None:
    raw = _normalize_text(text)
    if not raw:
        return None

    if any(word in raw for word in CANCEL_WORDS):
        return "cancel"
    if any(word in raw for word in CONFIRM_WORDS):
        return "confirm"
    return None


def extract_indexes_from_text(text: str) -> list[int]:
    raw = _normalize_text(text)
    if not raw:
        return []

    # Evita falsi positivi su orari/date (es. "domani alle 18").
    cleaned = re.sub(r"\balle\s*\d{1,2}(?:[:\.,]\d{2})?\b", " ", raw)
    cleaned = re.sub(r"\b\d{1,2}[:\.,]\d{2}\b", " ", cleaned)
    cleaned = re.sub(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", " ", cleaned)
    cleaned = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", cleaned)

    values: list[int] = []

    # "i primi due", "prime 3", "i primi 2"
    first_n_match = re.search(
        r"\bprim[ioe]\s+(\d{1,2}|uno|una|due|tre|quattro|cinque)\b",
        cleaned,
    )
    if first_n_match:
        token = first_n_match.group(1)
        n = int(token) if token.isdigit() else NUMBER_WORDS.get(token, 0)
        if 1 <= n <= 10:
            values.extend(list(range(1, n + 1)))

    # Ordinali testuali.
    for word, idx in ORDINALS.items():
        if re.search(rf"\b{word}\b", cleaned):
            values.append(idx)

    # Numeri espliciti, evitando orari/date e numeri troppo alti.
    for match in re.finditer(r"\b\d{1,2}\b", cleaned):
        num = int(match.group(0))
        if 1 <= num <= 30:
            values.append(num)

    seen: set[int] = set()
    unique: list[int] = []
    for idx in values:
        if idx not in seen:
            seen.add(idx)
            unique.append(idx)
    return unique


def extract_entity_reference(text: str) -> str | None:
    raw = _normalize_text(text)
    if not raw:
        return None

    if any(token in raw for token in ["quello", "quella", "quelli", "quelle"]):
        if "altro" in raw or "altra" in raw:
            return "other"
        return "that"

    if any(token in raw for token in ["ultimo", "ultima", "l'ultimo", "l ultima"]):
        return "last"

    if any(token in raw for token in ["primo", "prima"]):
        return "first"

    return None


def extract_time_from_text(text: str) -> tuple[int, int] | None:
    raw = _normalize_text(text)
    if not raw:
        return None

    match = re.search(r"\balle\s*(\d{1,2})(?:[:\.,](\d{2}))?\b", raw)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or "00")
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute

    match = re.search(r"\b(\d{1,2})[:\.,](\d{2})\b", raw)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute

    match = re.search(r"\balle\s*(\d{1,2})\b", raw)
    if match:
        hour = int(match.group(1))
        if 0 <= hour <= 23:
            return hour, 0

    return None


def _default_time_for_text(text: str) -> tuple[int, int]:
    raw = _normalize_text(text)
    if "mattina" in raw:
        return 9, 0
    if "pomeriggio" in raw:
        return 15, 0
    if "sera" in raw or "stasera" in raw:
        return 20, 0
    return 9, 0


def parse_day_period(text: str, now: datetime | None = None, tz: ZoneInfo = ROME_TZ) -> datetime | None:
    raw = _normalize_text(text)
    current = (now or datetime.now(tz)).astimezone(tz)

    def _at(day_delta: int, hour: int, minute: int) -> datetime:
        base = current + timedelta(days=day_delta)
        return base.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if "stasera" in raw:
        hour, minute = extract_time_from_text(raw) or (20, 0)
        candidate = _at(0, hour, minute)
        if candidate <= current:
            candidate = _at(1, hour, minute)
        return candidate

    if "domani mattina" in raw:
        return _at(1, 9, 0)
    if "domani pomeriggio" in raw:
        return _at(1, 15, 0)
    if "domani sera" in raw:
        return _at(1, 20, 0)

    if re.search(r"\bdomani\b", raw):
        hour, minute = extract_time_from_text(raw) or _default_time_for_text(raw)
        return _at(1, hour, minute)

    if re.search(r"\bdopodomani\b", raw):
        hour, minute = extract_time_from_text(raw) or _default_time_for_text(raw)
        return _at(2, hour, minute)

    if "weekend" in raw or "fine settimana" in raw:
        # Prossimo sabato alle 10:00, salvo orario esplicito.
        target_weekday = 5  # sabato
        delta = (target_weekday - current.weekday()) % 7
        if delta == 0 and current.hour >= 10:
            delta = 7
        hour, minute = extract_time_from_text(raw) or (10, 0)
        return _at(delta, hour, minute)

    return None


def _find_explicit_date_token(text: str) -> str | None:
    raw = _normalize_text(text)

    iso = re.search(r"\b\d{4}-\d{2}-\d{2}\b", raw)
    if iso:
        return iso.group(0)

    slash = re.search(r"\b\d{1,2}/\d{1,2}(?:/\d{4})?\b", raw)
    if slash:
        return slash.group(0)

    months_pattern = "|".join(ITALIAN_MONTHS.keys())
    text_date = re.search(
        rf"\b\d{{1,2}}\s+(?:{months_pattern})(?:\s+\d{{4}})?\b",
        raw,
    )
    if text_date:
        return text_date.group(0)

    return None


def parse_date_expression(text: str, base_dt: datetime | None = None) -> date | None:
    raw = _normalize_text(text)
    if not raw:
        return None

    current = (base_dt or now_rome()).astimezone(ROME_TZ)
    today = current.date()

    if re.search(r"\bdopodomani\b", raw):
        return today + timedelta(days=2)
    if re.search(r"\bdomani\b", raw):
        return today + timedelta(days=1)
    if re.search(r"\boggi\b", raw):
        return today

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            return None

    slash = re.fullmatch(r"(\d{1,2})/(\d{1,2})(?:/(\d{4}))?", raw)
    if slash:
        day = int(slash.group(1))
        month = int(slash.group(2))
        year = int(slash.group(3) or today.year)
        try:
            parsed = date(year, month, day)
        except ValueError:
            return None
        if not slash.group(3) and parsed < today:
            try:
                parsed = date(year + 1, month, day)
            except ValueError:
                return None
        return parsed

    months_pattern = "|".join(ITALIAN_MONTHS.keys())
    text_match = re.fullmatch(
        rf"(\d{{1,2}})\s+({months_pattern})(?:\s+(\d{{4}}))?",
        raw,
    )
    if text_match:
        day = int(text_match.group(1))
        month = ITALIAN_MONTHS[text_match.group(2)]
        year = int(text_match.group(3) or today.year)
        try:
            parsed = date(year, month, day)
        except ValueError:
            return None
        if not text_match.group(3) and parsed < today:
            try:
                parsed = date(year + 1, month, day)
            except ValueError:
                return None
        return parsed

    for weekday_name, weekday_idx in WEEKDAYS.items():
        if re.search(rf"\b{weekday_name}\b", raw):
            force_next_week = "prossim" in raw
            delta = (weekday_idx - today.weekday()) % 7
            if delta == 0:
                delta = 7
            if force_next_week:
                delta += 7
            return today + timedelta(days=delta)

    token = _find_explicit_date_token(raw)
    if token and token != raw:
        return parse_date_expression(token, base_dt=current)

    return None


def _parse_deadline_expression(raw: str, now: datetime) -> datetime | None:
    # "entro le 11 oggi", "entro le 18"
    match = re.search(r"\bentro\s+le\s+(\d{1,2})(?::(\d{2}))?(?:\s+oggi)?\b", raw)
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2) or "00")
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now and "oggi" not in raw:
        candidate += timedelta(days=1)
    return candidate


def parse_relative_datetime(
    text: str,
    now: datetime | None = None,
    tz: ZoneInfo = ROME_TZ,
) -> datetime | None:
    raw = _normalize_text(text)
    if not raw:
        return None

    current = (now or datetime.now(tz)).astimezone(tz)

    if re.search(r"\b(?:fra|tra)\s+mezz'?ora\b", raw):
        return current + timedelta(minutes=30)

    match = re.search(r"\b(?:tra|fra)\s+(\d+)\s+minut[oi]\b", raw)
    if match:
        return current + timedelta(minutes=int(match.group(1)))

    match = re.search(r"\b(?:tra|fra)\s+(\d+)\s+or[ae]\b", raw)
    if match:
        return current + timedelta(hours=int(match.group(1)))

    match = re.search(r"\b(?:tra|fra)\s+(\d+)\s+giorn[oi]\b", raw)
    if match:
        target = current + timedelta(days=int(match.group(1)))
        hour, minute = extract_time_from_text(raw) or _default_time_for_text(raw)
        return target.replace(hour=hour, minute=minute, second=0, microsecond=0)

    deadline = _parse_deadline_expression(raw, current)
    if deadline:
        return deadline

    period_dt = parse_day_period(raw, now=current, tz=tz)
    if period_dt:
        return period_dt

    target_date = parse_date_expression(raw, base_dt=current)
    if target_date:
        hour, minute = extract_time_from_text(raw) or _default_time_for_text(raw)
        return datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            hour,
            minute,
            tzinfo=tz,
        )

    token = _find_explicit_date_token(raw)
    if token:
        target_date = parse_date_expression(token, base_dt=current)
        if target_date:
            hour, minute = extract_time_from_text(raw) or _default_time_for_text(raw)
            return datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                hour,
                minute,
                tzinfo=tz,
            )

    return None


def resolve_due_datetime(
    text: str,
    now: datetime | None = None,
    tz: ZoneInfo = ROME_TZ,
) -> datetime | None:
    current = (now or datetime.now(tz)).astimezone(tz)
    parsed = parse_relative_datetime(text, now=current, tz=tz)
    if parsed:
        return parsed

    target_date = parse_date_expression(text, base_dt=current)
    if target_date:
        hour, minute = extract_time_from_text(text) or _default_time_for_text(text)
        return datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            hour,
            minute,
            tzinfo=tz,
        )

    return None


def extract_due_date_time(
    text: str,
    base_dt: datetime | None = None,
) -> tuple[str, str] | None:
    parsed = resolve_due_datetime(text, now=base_dt or now_rome(), tz=ROME_TZ)
    if not parsed:
        return None
    return parsed.strftime("%Y-%m-%d"), parsed.strftime("%H:%M")


def extract_date_for_query(text: str, base_dt: datetime | None = None) -> str | None:
    parsed_date = parse_date_expression(text, base_dt=base_dt)
    if parsed_date:
        return parsed_date.isoformat()

    token = _find_explicit_date_token(text)
    if not token:
        return None

    parsed_date = parse_date_expression(token, base_dt=base_dt)
    return parsed_date.isoformat() if parsed_date else None
