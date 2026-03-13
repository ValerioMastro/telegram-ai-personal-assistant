from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from time_parser import now_rome, parse_date_expression

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
ROME_TZ = ZoneInfo("Europe/Rome")
CREDENTIALS_FILE = Path(__file__).resolve().parent / "credentials.json"
TOKEN_FILE = Path(__file__).resolve().parent / "token.json"


class CalendarError(RuntimeError):
    pass


def _normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _normalize_time(time_str: str) -> str:
    raw = (time_str or "").strip().lower()
    if not raw:
        raise ValueError("Orario mancante.")

    if re.fullmatch(r"\d{1,2}", raw):
        raw = f"{int(raw):02d}:00"

    try:
        datetime.strptime(raw, "%H:%M")
    except ValueError as exc:
        raise ValueError("Formato orario non valido. Usa HH:MM.") from exc
    return raw


def _resolve_date(date_input: str) -> date:
    raw = (date_input or "").strip()
    if not raw:
        raise ValueError("Data mancante.")

    parsed = parse_date_expression(raw, base_dt=now_rome())
    if parsed:
        return parsed

    raise ValueError(f"Data non riconosciuta: {date_input}")


def _ensure_token_dir() -> None:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)


def get_calendar_service():
    creds = None
    try:
        if TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not CREDENTIALS_FILE.exists():
                    raise CalendarError(
                        f"credentials.json non trovato: {CREDENTIALS_FILE}"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CREDENTIALS_FILE),
                    SCOPES,
                )
                creds = flow.run_local_server(port=0)

            _ensure_token_dir()
            TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

        return build("calendar", "v3", credentials=creds, cache_discovery=False)
    except CalendarError:
        raise
    except Exception as exc:
        raise CalendarError(f"Impossibile inizializzare Google Calendar: {exc}") from exc


def _normalize_event(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "summary": item.get("summary", "Senza titolo"),
        "description": item.get("description", ""),
        "start": item.get("start", {}),
        "end": item.get("end", {}),
        "htmlLink": item.get("htmlLink", ""),
    }


def _list_events_between(start_dt: datetime, end_dt: datetime) -> list[dict]:
    service = get_calendar_service()
    try:
        response = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_dt.isoformat(),
                timeMax=end_dt.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        items = response.get("items", [])
        return [_normalize_event(item) for item in items]
    except HttpError as exc:
        raise CalendarError(f"Errore API Google Calendar: {exc}") from exc
    except Exception as exc:
        raise CalendarError(f"Errore nel recupero eventi: {exc}") from exc


def _day_bounds(target_day: date) -> tuple[datetime, datetime]:
    start_dt = datetime(
        year=target_day.year,
        month=target_day.month,
        day=target_day.day,
        hour=0,
        minute=0,
        tzinfo=ROME_TZ,
    )
    end_dt = start_dt + timedelta(days=1)
    return start_dt, end_dt


def _parse_datetime_on_day(day: date, time_str: str) -> datetime:
    clean_time = _normalize_time(time_str)
    return datetime.strptime(
        f"{day.isoformat()} {clean_time}",
        "%Y-%m-%d %H:%M",
    ).replace(tzinfo=ROME_TZ)


def create_calendar_event(
    title: str,
    date_str: str,
    time_str: str,
    duration_minutes: int = 60,
    notes: str = "",
) -> dict:
    clean_title = (title or "").strip()
    if not clean_title:
        raise ValueError("Titolo evento vuoto.")

    target_day = _resolve_date(date_str)
    clean_time = _normalize_time(time_str)

    try:
        duration = int(duration_minutes)
    except Exception:
        duration = 60
    if duration <= 0:
        duration = 60

    start_naive = datetime.strptime(
        f"{target_day.isoformat()} {clean_time}",
        "%Y-%m-%d %H:%M",
    )
    start_dt = start_naive.replace(tzinfo=ROME_TZ)
    end_dt = start_dt + timedelta(minutes=duration)

    payload = {
        "summary": clean_title,
        "description": (notes or "").strip(),
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Europe/Rome"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "Europe/Rome"},
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 30}],
        },
    }

    service = get_calendar_service()
    try:
        created = (
            service.events()
            .insert(calendarId="primary", body=payload, sendUpdates="none")
            .execute()
        )
        return _normalize_event(created)
    except HttpError as exc:
        raise CalendarError(f"Errore creazione evento: {exc}") from exc
    except Exception as exc:
        raise CalendarError(f"Impossibile creare evento: {exc}") from exc


def get_calendar_event(event_id: str) -> dict:
    clean_event_id = (event_id or "").strip()
    if not clean_event_id:
        raise ValueError("event_id mancante.")

    service = get_calendar_service()
    try:
        event = service.events().get(calendarId="primary", eventId=clean_event_id).execute()
        return _normalize_event(event)
    except HttpError as exc:
        raise CalendarError(f"Errore recupero evento: {exc}") from exc
    except Exception as exc:
        raise CalendarError(f"Impossibile recuperare evento: {exc}") from exc


def delete_calendar_event(event_id: str) -> dict:
    clean_event_id = (event_id or "").strip()
    if not clean_event_id:
        raise ValueError("event_id mancante.")

    service = get_calendar_service()
    try:
        service.events().delete(calendarId="primary", eventId=clean_event_id).execute()
        return {"deleted": True, "event_id": clean_event_id}
    except HttpError as exc:
        raise CalendarError(f"Errore cancellazione evento: {exc}") from exc
    except Exception as exc:
        raise CalendarError(f"Impossibile cancellare evento: {exc}") from exc


def delete_calendar_events(event_ids: list[str]) -> dict:
    deleted: list[str] = []
    failed: list[str] = []

    for event_id in event_ids:
        try:
            delete_calendar_event(event_id)
            deleted.append(event_id)
        except Exception:
            failed.append(event_id)

    return {
        "deleted_count": len(deleted),
        "failed_count": len(failed),
        "deleted": deleted,
        "failed": failed,
    }


def update_calendar_event(
    event_id: str,
    new_date: str | None = None,
    new_time: str | None = None,
    new_title: str | None = None,
    new_notes: str | None = None,
) -> dict:
    clean_event_id = (event_id or "").strip()
    if not clean_event_id:
        raise ValueError("event_id mancante.")

    service = get_calendar_service()
    try:
        event = service.events().get(calendarId="primary", eventId=clean_event_id).execute()
    except HttpError as exc:
        raise CalendarError(f"Errore recupero evento: {exc}") from exc
    except Exception as exc:
        raise CalendarError(f"Impossibile recuperare evento: {exc}") from exc

    start_raw = event.get("start", {}).get("dateTime")
    end_raw = event.get("end", {}).get("dateTime")

    # fallback per eventi all-day
    if start_raw:
        start_dt = datetime.fromisoformat(start_raw).astimezone(ROME_TZ)
    else:
        start_date = event.get("start", {}).get("date")
        if not start_date:
            raise CalendarError("Evento senza start valido.")
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(
            hour=9,
            minute=0,
            tzinfo=ROME_TZ,
        )

    if end_raw:
        end_dt = datetime.fromisoformat(end_raw).astimezone(ROME_TZ)
    else:
        end_date = event.get("end", {}).get("date")
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(
                hour=10,
                minute=0,
                tzinfo=ROME_TZ,
            )
        else:
            end_dt = start_dt + timedelta(minutes=60)

    duration = end_dt - start_dt
    if duration <= timedelta(minutes=0):
        duration = timedelta(minutes=60)

    target_date = _resolve_date(new_date) if new_date else start_dt.date()
    target_time = _normalize_time(new_time) if new_time else start_dt.strftime("%H:%M")
    target_start = datetime.strptime(
        f"{target_date.isoformat()} {target_time}",
        "%Y-%m-%d %H:%M",
    ).replace(tzinfo=ROME_TZ)
    target_end = target_start + duration

    if new_title is not None:
        event["summary"] = (new_title or "").strip() or event.get("summary", "Senza titolo")

    if new_notes is not None:
        event["description"] = (new_notes or "").strip()

    event["start"] = {"dateTime": target_start.isoformat(), "timeZone": "Europe/Rome"}
    event["end"] = {"dateTime": target_end.isoformat(), "timeZone": "Europe/Rome"}

    try:
        updated = (
            service.events()
            .patch(calendarId="primary", eventId=clean_event_id, body=event)
            .execute()
        )
        return _normalize_event(updated)
    except HttpError as exc:
        raise CalendarError(f"Errore aggiornamento evento: {exc}") from exc
    except Exception as exc:
        raise CalendarError(f"Impossibile aggiornare evento: {exc}") from exc


def get_today_events() -> list[dict]:
    start_dt, end_dt = _day_bounds(now_rome().date())
    return _list_events_between(start_dt, end_dt)


def get_tomorrow_events() -> list[dict]:
    start_dt, end_dt = _day_bounds(now_rome().date() + timedelta(days=1))
    return _list_events_between(start_dt, end_dt)


def get_events_for_date(date_str: str) -> list[dict]:
    target_day = _resolve_date(date_str)
    start_dt, end_dt = _day_bounds(target_day)
    return _list_events_between(start_dt, end_dt)


def get_events_for_next_days(days: int = 7, from_dt: datetime | None = None) -> list[dict]:
    safe_days = max(1, int(days))
    start_dt = (from_dt or now_rome()).astimezone(ROME_TZ)
    end_dt = start_dt + timedelta(days=safe_days)
    return _list_events_between(start_dt, end_dt)


def get_upcoming_events(within_minutes: int = 30, now: datetime | None = None) -> list[dict]:
    current = (now or now_rome()).astimezone(ROME_TZ)
    safe_minutes = max(1, int(within_minutes))
    end_dt = current + timedelta(minutes=safe_minutes)
    return _list_events_between(current, end_dt)


def find_similar_event(
    title: str,
    date_str: str,
    time_str: str,
    window_minutes: int = 120,
    limit: int = 3,
) -> list[dict]:
    clean_title = _normalize_text(title)
    if not clean_title:
        return []

    target_day = _resolve_date(date_str)
    target_dt = _parse_datetime_on_day(target_day, time_str)
    safe_window = max(15, int(window_minutes))

    candidates = get_events_for_date(target_day.isoformat())
    matches: list[tuple[int, dict]] = []

    for event in candidates:
        event_title = _normalize_text(event.get("summary", ""))
        if not event_title:
            continue

        if event_title == clean_title:
            title_score = 100
        elif clean_title in event_title or event_title in clean_title:
            title_score = 85
        else:
            # Somiglianza semplice basata su token in comune.
            target_words = set(clean_title.split())
            event_words = set(event_title.split())
            inter = len(target_words & event_words)
            union = len(target_words | event_words) or 1
            title_score = int((inter / union) * 100)

        if title_score < 60:
            continue

        start_raw = event.get("start", {}).get("dateTime")
        if not start_raw:
            # Evento all-day: se il titolo e' molto vicino lo consideriamo duplicato.
            if title_score >= 85:
                matches.append((title_score, event))
            continue

        try:
            event_dt = datetime.fromisoformat(start_raw).astimezone(ROME_TZ)
        except Exception:
            continue

        delta_minutes = abs((event_dt - target_dt).total_seconds()) / 60
        if delta_minutes <= safe_window and title_score >= 70:
            # Bonus se orario molto vicino.
            score = title_score + (20 if delta_minutes <= 30 else 10)
            matches.append((score, event))

    matches.sort(key=lambda x: x[0], reverse=True)
    return [event for _, event in matches[: max(1, int(limit))]]


def get_calendar_event_by_order(date_str: str, order: int) -> dict:
    try:
        selected_order = int(order)
    except Exception as exc:
        raise ValueError("Ordine evento non valido.") from exc

    if selected_order <= 0:
        raise ValueError("Ordine evento deve essere >= 1.")

    events = get_events_for_date(date_str)
    if not events:
        raise ValueError("Nessun evento trovato per la data richiesta.")

    index = selected_order - 1
    if index >= len(events):
        raise ValueError(
            f"Ordine evento non valido: {selected_order}. Eventi disponibili: {len(events)}"
        )

    event = events[index]
    if not event.get("id"):
        raise CalendarError("Evento senza id: impossibile cancellare.")

    return {
        "event_id": event["id"],
        "order": selected_order,
        "summary": event.get("summary", "Senza titolo"),
        "start": event.get("start", {}),
        "date": _resolve_date(date_str).isoformat(),
    }


def delete_calendar_event_by_order(date_str: str, order: int) -> dict:
    selected = get_calendar_event_by_order(date_str=date_str, order=order)
    delete_calendar_event(selected["event_id"])
    return {
        "deleted": True,
        "event_id": selected["event_id"],
        "order": selected["order"],
        "summary": selected["summary"],
        "date": selected["date"],
    }


def _event_from_context_index(items: list[dict], index: int) -> dict:
    if not isinstance(items, list):
        raise ValueError("Contesto eventi non valido.")
    for item in items:
        try:
            if int(item.get("index")) == int(index):
                if not item.get("event_id"):
                    raise ValueError("Evento senza ID nel contesto.")
                return item
        except Exception:
            continue
    raise ValueError("Indice evento non trovato nel contesto.")


def delete_calendar_event_by_index(items: list[dict], index: int) -> dict:
    selected = _event_from_context_index(items, index)
    return delete_calendar_event(str(selected["event_id"]))


def delete_calendar_events_by_indexes(items: list[dict], indexes: list[int]) -> dict:
    event_ids: list[str] = []
    for idx in indexes:
        try:
            selected = _event_from_context_index(items, int(idx))
            event_ids.append(str(selected["event_id"]))
        except Exception:
            continue
    return delete_calendar_events(event_ids)


def calendar_update_event_by_index(
    items: list[dict],
    index: int,
    new_date: str | None = None,
    new_time: str | None = None,
    new_title: str | None = None,
    new_notes: str | None = None,
) -> dict:
    selected = _event_from_context_index(items, index)
    return update_calendar_event(
        event_id=str(selected["event_id"]),
        new_date=new_date,
        new_time=new_time,
        new_title=new_title,
        new_notes=new_notes,
    )


def calendar_move_event_by_index(items: list[dict], index: int, new_date: str, new_time: str) -> dict:
    return calendar_update_event_by_index(
        items=items,
        index=index,
        new_date=new_date,
        new_time=new_time,
    )


def detect_calendar_conflict(
    date_str: str,
    time_str: str,
    duration_minutes: int = 60,
) -> dict:
    target_day = _resolve_date(date_str)
    target_start = _parse_datetime_on_day(target_day, time_str)
    safe_duration = max(1, int(duration_minutes))
    target_end = target_start + timedelta(minutes=safe_duration)

    conflicts: list[dict] = []
    for event in get_events_for_date(target_day.isoformat()):
        start_raw = event.get("start", {}).get("dateTime")
        end_raw = event.get("end", {}).get("dateTime")

        if not start_raw or not end_raw:
            # evento all-day: consideralo sempre in conflitto
            if event.get("start", {}).get("date"):
                conflicts.append(event)
            continue

        try:
            event_start = datetime.fromisoformat(start_raw).astimezone(ROME_TZ)
            event_end = datetime.fromisoformat(end_raw).astimezone(ROME_TZ)
        except Exception:
            continue

        if target_start < event_end and target_end > event_start:
            conflicts.append(event)

    return {
        "has_conflict": bool(conflicts),
        "conflicts": conflicts,
        "target_start": target_start.isoformat(),
        "target_end": target_end.isoformat(),
    }


def find_free_slots(
    date_str: str,
    start_hour: int = 8,
    end_hour: int = 22,
    slot_minutes: int = 60,
) -> list[dict]:
    target_day = _resolve_date(date_str)
    safe_start_hour = max(0, min(23, int(start_hour)))
    safe_end_hour = max(safe_start_hour + 1, min(24, int(end_hour)))
    safe_slot = max(15, int(slot_minutes))

    day_start = datetime(
        target_day.year,
        target_day.month,
        target_day.day,
        safe_start_hour,
        0,
        tzinfo=ROME_TZ,
    )
    day_end = datetime(
        target_day.year,
        target_day.month,
        target_day.day,
        safe_end_hour,
        0,
        tzinfo=ROME_TZ,
    )

    busy: list[tuple[datetime, datetime]] = []
    for event in get_events_for_date(target_day.isoformat()):
        start_raw = event.get("start", {}).get("dateTime")
        end_raw = event.get("end", {}).get("dateTime")
        if not start_raw or not end_raw:
            if event.get("start", {}).get("date"):
                busy.append((day_start, day_end))
            continue
        try:
            start_dt = datetime.fromisoformat(start_raw).astimezone(ROME_TZ)
            end_dt = datetime.fromisoformat(end_raw).astimezone(ROME_TZ)
        except Exception:
            continue
        busy.append((max(start_dt, day_start), min(end_dt, day_end)))

    busy = [interval for interval in busy if interval[0] < interval[1]]
    busy.sort(key=lambda x: x[0])

    merged: list[tuple[datetime, datetime]] = []
    for interval in busy:
        if not merged:
            merged.append(interval)
            continue
        last_start, last_end = merged[-1]
        cur_start, cur_end = interval
        if cur_start <= last_end:
            merged[-1] = (last_start, max(last_end, cur_end))
        else:
            merged.append(interval)

    free_slots: list[dict] = []
    cursor = day_start
    for start_dt, end_dt in merged:
        if start_dt - cursor >= timedelta(minutes=safe_slot):
            free_slots.append(
                {
                    "start": cursor.isoformat(),
                    "end": start_dt.isoformat(),
                }
            )
        cursor = max(cursor, end_dt)

    if day_end - cursor >= timedelta(minutes=safe_slot):
        free_slots.append(
            {
                "start": cursor.isoformat(),
                "end": day_end.isoformat(),
            }
        )

    return free_slots


def suggest_free_slot_for_event(
    date_str: str,
    duration_minutes: int = 60,
    preferred_time: str | None = None,
) -> dict:
    safe_duration = max(15, int(duration_minutes))
    if preferred_time:
        conflict = detect_calendar_conflict(
            date_str=date_str,
            time_str=preferred_time,
            duration_minutes=safe_duration,
        )
        if not conflict["has_conflict"]:
            target_day = _resolve_date(date_str)
            preferred_start = _parse_datetime_on_day(target_day, preferred_time)
            return {
                "date": target_day.isoformat(),
                "time": preferred_start.strftime("%H:%M"),
                "reason": "preferred_available",
            }

    for slot in find_free_slots(date_str=date_str, slot_minutes=safe_duration):
        try:
            start_dt = datetime.fromisoformat(slot["start"]).astimezone(ROME_TZ)
            end_dt = datetime.fromisoformat(slot["end"]).astimezone(ROME_TZ)
        except Exception:
            continue
        if end_dt - start_dt >= timedelta(minutes=safe_duration):
            return {
                "date": start_dt.date().isoformat(),
                "time": start_dt.strftime("%H:%M"),
                "reason": "first_free_slot",
            }

    return {
        "date": _resolve_date(date_str).isoformat(),
        "time": None,
        "reason": "no_slot_found",
    }
