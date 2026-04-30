"""Iter29 - Trial 7 días + cadencia de emails (halfway, warn, expired) + ajustes."""
import pytest
from email_service import EmailService
from routers.coach import TRIAL_DURATION_DAYS, TRIAL_WARN_THRESHOLD_DAYS, _trial_days_left
from datetime import datetime, timezone, timedelta


def test_trial_duration_is_7_days():
    assert TRIAL_DURATION_DAYS == 7


def test_trial_warn_threshold_is_3_days():
    assert TRIAL_WARN_THRESHOLD_DAYS == 3


def test_trial_days_left_active_returns_none():
    tenant = {"subscription_status": "active",
              "created_at": datetime.now(timezone.utc).isoformat()}
    assert _trial_days_left(tenant) is None


def test_trial_days_left_counts_down_correctly():
    created = datetime.now(timezone.utc) - timedelta(days=3)
    tenant = {"subscription_status": "trialing", "created_at": created.isoformat()}
    # 7 - 3 = 4 días left
    assert _trial_days_left(tenant) == 4


def test_trial_days_left_zero_at_end():
    created = datetime.now(timezone.utc) - timedelta(days=7)
    tenant = {"subscription_status": "trialing", "created_at": created.isoformat()}
    assert _trial_days_left(tenant) == 0


def test_trial_days_left_never_negative():
    created = datetime.now(timezone.utc) - timedelta(days=15)
    tenant = {"subscription_status": "trialing", "created_at": created.isoformat()}
    assert _trial_days_left(tenant) == 0


@pytest.mark.asyncio
async def test_send_trial_halfway_exists_and_shape():
    svc = EmailService(db=None)
    svc.smtp_username = "u"
    svc.smtp_password = "p"
    captured = {}

    async def fake_send(**kwargs):
        captured.update(kwargs)
        return True

    svc.send_email = fake_send  # type: ignore
    ok = await svc.send_trial_halfway(
        to_email="a@b.com", business_name="Acme",
        days_left=4, upgrade_url="https://x/config",
    )
    assert ok is True
    assert captured["to_emails"] == ["a@b.com"]
    assert "Acme" in captured["subject"]
    assert "mitad" in captured["html_body"].lower() or "mitad" in captured["subject"].lower()
    assert "4 d" in captured["html_body"]


@pytest.mark.asyncio
async def test_send_trial_expired_exists_and_shape():
    svc = EmailService(db=None)
    svc.smtp_username = "u"
    svc.smtp_password = "p"
    captured = {}

    async def fake_send(**kwargs):
        captured.update(kwargs)
        return True

    svc.send_email = fake_send  # type: ignore
    ok = await svc.send_trial_expired(
        to_email="a@b.com", business_name="Acme",
        upgrade_url="https://x/config",
    )
    assert ok is True
    assert "terminó" in captured["subject"] or "termin" in captured["subject"]
    assert "30 días" in captured["html_body"]  # retención post-trial
    assert "Reactivar" in captured["html_body"] or "reactiv" in captured["html_body"].lower()


@pytest.mark.asyncio
async def test_trial_emails_skipped_when_no_smtp():
    svc = EmailService(db=None)
    svc.smtp_username = None
    svc.smtp_password = None
    # Todos retornan False sin lanzar
    assert await svc.send_trial_halfway("x@y.com", "B", 4, "u") is False
    assert await svc.send_trial_expired("x@y.com", "B", "u") is False
    # Empty email también
    assert await svc.send_trial_halfway("", "B", 4, "u") is False
    assert await svc.send_trial_expired("", "B", "u") is False


@pytest.mark.asyncio
async def test_welcome_email_says_7_days_not_14():
    svc = EmailService(db=None)
    svc.smtp_username = "u"
    svc.smtp_password = "p"
    captured = {}

    async def fake_send(**kwargs):
        captured.update(kwargs)
        return True

    svc.send_email = fake_send  # type: ignore
    await svc.send_welcome_tenant(
        to_email="x@y.com", business_name="Acme",
        tenant_id="acme", admin_name="María",
    )
    # NO debe aparecer "14 días"
    assert "14 días" not in captured["html_body"]
    assert "14 días" not in captured["text_body"]
    # SÍ debe aparecer "7 días"
    assert "7 días" in captured["html_body"] or "7 días" in captured["text_body"]
