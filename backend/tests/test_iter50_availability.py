"""
Tests para la lógica de disponibilidad en Google Calendar.

La lógica pura (is_slot_busy, find_alternative_slots) es testeable sin DB
ni red. Los tests mockean la lista de events tal como Calendar API la
devolvería.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google_calendar_service import (
    is_slot_busy,
    find_alternative_slots,
    _parse_event_datetime,
)


def _mk_event(start, end, summary="Cita", transparency=None):
    """Helper para crear un evento con el shape de Google Calendar API."""
    ev = {
        "id": f"ev_{start.isoformat()}",
        "summary": summary,
        "start": {"dateTime": start.isoformat(), "timeZone": "America/Argentina/Buenos_Aires"},
        "end": {"dateTime": end.isoformat(), "timeZone": "America/Argentina/Buenos_Aires"},
    }
    if transparency:
        ev["transparency"] = transparency
    return ev


def test_is_slot_busy_detects_overlap():
    # Evento de 10:00 a 11:00
    ev_start = datetime(2026, 5, 10, 10, 0, tzinfo=timezone.utc)
    ev_end = datetime(2026, 5, 10, 11, 0, tzinfo=timezone.utc)
    events = [_mk_event(ev_start, ev_end)]

    # Slot 10:30-11:30 solapa
    assert is_slot_busy(
        events,
        datetime(2026, 5, 10, 10, 30, tzinfo=timezone.utc),
        datetime(2026, 5, 10, 11, 30, tzinfo=timezone.utc),
    ) is True


def test_is_slot_busy_free_when_adjacent_not_overlapping():
    ev_start = datetime(2026, 5, 10, 10, 0, tzinfo=timezone.utc)
    ev_end = datetime(2026, 5, 10, 11, 0, tzinfo=timezone.utc)
    events = [_mk_event(ev_start, ev_end)]

    # Slot 11:00-12:00 justo al final del evento → NO solapa
    assert is_slot_busy(
        events,
        datetime(2026, 5, 10, 11, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc),
    ) is False


def test_is_slot_busy_ignores_transparent_events():
    """Eventos marcados como 'Libre' no bloquean el slot."""
    ev_start = datetime(2026, 5, 10, 10, 0, tzinfo=timezone.utc)
    ev_end = datetime(2026, 5, 10, 11, 0, tzinfo=timezone.utc)
    events = [_mk_event(ev_start, ev_end, transparency="transparent")]
    assert is_slot_busy(events, ev_start, ev_end) is False


def test_is_slot_busy_empty_events():
    assert is_slot_busy([], datetime(2026, 5, 10, 10, 0, tzinfo=timezone.utc),
                        datetime(2026, 5, 10, 11, 0, tzinfo=timezone.utc)) is False


def test_parse_event_datetime_handles_all_day_events():
    """Eventos all-day usan `date` en lugar de `dateTime`."""
    ev = {"start": {"date": "2026-05-10"}, "end": {"date": "2026-05-11"}}
    start = _parse_event_datetime(ev, "start")
    assert start is not None
    assert start.year == 2026 and start.month == 5 and start.day == 10


def test_find_alternative_slots_returns_empty_when_no_alternatives_in_window():
    """Si TODOS los horarios laborales están ocupados, devuelve []."""
    # Creamos eventos que cubren todo el horario 9-19 por 7 días
    events = []
    for day_offset in range(7):
        for hour in range(9, 19):
            s = datetime(2026, 5, 11, hour, 0, tzinfo=timezone.utc) + timedelta(days=day_offset)
            e = s + timedelta(hours=1)
            events.append(_mk_event(s, e))
    alts = find_alternative_slots(
        events,
        datetime(2026, 5, 11, 15, 0, tzinfo=timezone.utc),
        duration_minutes=60,
        max_days_ahead=7,
    )
    assert alts == []


def test_find_alternative_slots_proposes_3_nearby_free_slots():
    """Slot preferido 15:00 ocupado → debe proponer otros dentro del día o días cercanos."""
    events = [
        _mk_event(
            datetime(2026, 5, 11, 15, 0, tzinfo=timezone.utc),
            datetime(2026, 5, 11, 16, 0, tzinfo=timezone.utc),
        ),
    ]
    alts = find_alternative_slots(
        events,
        datetime(2026, 5, 11, 15, 0, tzinfo=timezone.utc),
        duration_minutes=60,
    )
    assert len(alts) == 3
    for a in alts:
        # Ninguna alternativa debe caer dentro del evento ocupado
        assert not is_slot_busy(
            events, a, a + timedelta(minutes=60),
        )


def test_find_alternative_slots_respects_business_hours():
    """Las alternativas deben estar dentro del horario laboral (9-19)."""
    events = [
        _mk_event(
            datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc),
            datetime(2026, 5, 11, 11, 0, tzinfo=timezone.utc),
        ),
    ]
    alts = find_alternative_slots(
        events,
        datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc),
        duration_minutes=60,
        business_hours=(9, 19),
    )
    for a in alts:
        assert 9 <= a.hour < 19, f"{a.hour} fuera de horario laboral"


def test_find_alternative_slots_skips_sundays():
    """Por default no propone domingos."""
    # 2026-05-10 era un domingo
    events = [
        _mk_event(
            datetime(2026, 5, 9, 15, 0, tzinfo=timezone.utc),  # sábado
            datetime(2026, 5, 9, 16, 0, tzinfo=timezone.utc),
        ),
    ]
    alts = find_alternative_slots(
        events,
        datetime(2026, 5, 9, 15, 0, tzinfo=timezone.utc),
        duration_minutes=60,
        max_days_ahead=7,
    )
    for a in alts:
        # Nunca debe caer en domingo (weekday=6)
        assert a.weekday() != 6, f"alternativa en domingo: {a}"


def test_find_alternative_slots_prefers_same_day_closer_hours():
    """Si el slot de las 15:00 está ocupado pero las 14:00 y 16:00 están libres,
    debe proponer esas primero (cercanía horaria al preferido)."""
    events = [
        _mk_event(
            datetime(2026, 5, 11, 15, 0, tzinfo=timezone.utc),
            datetime(2026, 5, 11, 16, 0, tzinfo=timezone.utc),
        ),
    ]
    alts = find_alternative_slots(
        events,
        datetime(2026, 5, 11, 15, 0, tzinfo=timezone.utc),
        duration_minutes=60,
        max_alternatives=3,
    )
    assert len(alts) >= 1
    # La primera alternativa debe ser del MISMO día (no saltar al día siguiente si hay libre ese día)
    assert alts[0].date() == datetime(2026, 5, 11).date()
    # Y las horas más cercanas (14 o 16) deben aparecer antes que las más lejanas
    hours = [a.hour for a in alts if a.date() == datetime(2026, 5, 11).date()]
    assert 14 in hours or 16 in hours, f"esperaba 14 o 16 en {hours}"


def test_find_alternative_slots_respects_max_alternatives():
    alts = find_alternative_slots(
        [],  # todo libre
        datetime(2026, 5, 11, 15, 0, tzinfo=timezone.utc),
        duration_minutes=60,
        max_alternatives=2,
    )
    assert len(alts) == 2
