"""Iter27 - Welcome email on tenant signup + bcrypt pin + locust stress test scaffold.

Tests:
- Tenant onboarding triggers send_welcome_tenant best-effort.
- send_welcome_tenant skip silencioso si SMTP no config.
- send_welcome_tenant produce HTML estructurado correcto cuando SMTP config.
- bcrypt version pineada (sin warning __about__).
"""
import os
import bcrypt
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from email_service import EmailService
from models import EmailType


# ============================================================
# bcrypt version pin (Paso 5)
# ============================================================

def test_bcrypt_version_pinned_to_4_0_x():
    """Pinear bcrypt a 4.0.x evita el warning '__about__' de passlib."""
    ver = bcrypt.__version__
    major = int(ver.split(".")[0])
    minor = int(ver.split(".")[1])
    assert major == 4
    assert minor == 0, f"bcrypt {ver} aún produce el warning de passlib"


def test_bcrypt_has_about_attribute():
    """passlib lee bcrypt.__about__.__version__. Si falta, hay warning."""
    assert hasattr(bcrypt, "__about__"), (
        "bcrypt sin __about__: passlib emitirá warnings ruidosos en logs"
    )
    assert hasattr(bcrypt.__about__, "__version__")


# ============================================================
# Welcome email (Paso 7)
# ============================================================

@pytest.mark.asyncio
async def test_send_welcome_tenant_skipped_when_smtp_not_configured():
    """Sin SMTP no debe levantar excepción: best-effort."""
    svc = EmailService(db=None)
    # Forzar no-config aunque .env tenga algo
    svc.smtp_username = None
    svc.smtp_password = None
    result = await svc.send_welcome_tenant(
        to_email="newtenant@example.com",
        business_name="Acme SA",
        tenant_id="acme-sa",
        admin_name="María Pérez",
    )
    assert result is False  # skipped, pero no lanzó


@pytest.mark.asyncio
async def test_send_welcome_tenant_skipped_when_no_email():
    svc = EmailService(db=None)
    svc.smtp_username = "x"
    svc.smtp_password = "y"
    result = await svc.send_welcome_tenant(
        to_email="",
        business_name="Acme",
        tenant_id="acme",
    )
    assert result is False


@pytest.mark.asyncio
async def test_send_welcome_tenant_calls_send_email_with_correct_shape():
    svc = EmailService(db=None)
    svc.smtp_username = "user"
    svc.smtp_password = "pass"
    svc.from_email = "noreply@inmobot.com"
    captured = {}

    async def fake_send(to_emails, subject, html_body, text_body=None,
                        email_type=None, lead_phone=None):
        captured["to_emails"] = to_emails
        captured["subject"] = subject
        captured["html_body"] = html_body
        captured["text_body"] = text_body
        captured["email_type"] = email_type
        return True

    svc.send_email = fake_send  # type: ignore
    ok = await svc.send_welcome_tenant(
        to_email="hi@acme.com",
        business_name="Acme SA",
        tenant_id="acme-sa",
        admin_name="María Pérez",
    )
    assert ok is True
    assert captured["to_emails"] == ["hi@acme.com"]
    assert "Bienvenido" in captured["subject"]
    assert "Acme SA" in captured["subject"]
    assert captured["email_type"] == EmailType.WELCOME_TENANT
    # HTML contiene CTA, business_name, primer nombre, tenant_id en landing
    assert "Acme SA" in captured["html_body"]
    assert "María" in captured["html_body"]
    assert "acme-sa" in captured["html_body"]  # link a /inicio/{tenant_id}
    assert "dashboard" in captured["html_body"].lower()
    # Text body es plain readable
    assert "Acme SA" in captured["text_body"]


@pytest.mark.asyncio
async def test_welcome_tenant_uses_business_name_when_admin_name_missing():
    svc = EmailService(db=None)
    svc.smtp_username = "u"
    svc.smtp_password = "p"
    captured = {}

    async def fake_send(**kwargs):
        captured.update(kwargs)
        return True

    svc.send_email = fake_send  # type: ignore
    await svc.send_welcome_tenant(
        to_email="x@y.com",
        business_name="Solo Negocio",
        tenant_id="solo-negocio",
        admin_name=None,
    )
    # Primer "palabra" del business_name actúa como first_name fallback
    assert "Solo" in captured["html_body"]


def test_email_type_welcome_tenant_exists():
    assert EmailType.WELCOME_TENANT.value == "welcome_tenant"


# ============================================================
# Locust scaffold (Paso 9) — verifica que el archivo existe y es importable
# ============================================================

def test_locustfile_exists_and_imports():
    """No corremos locust en CI, pero validamos que el scaffold sea importable."""
    import importlib.util
    path = os.path.join(os.path.dirname(__file__), "..", "..", "load_tests", "locustfile.py")
    path = os.path.abspath(path)
    assert os.path.exists(path), f"locustfile no encontrado en {path}"
    spec = importlib.util.spec_from_file_location("locustfile_test", path)
    # No ejecutamos (locust import puede fallar en CI sin la lib instalada),
    # solo validamos sintaxis con compile():
    with open(path, "r") as f:
        source = f.read()
    compile(source, path, "exec")  # AST valid
    assert "PublicVisitor" in source
    assert "AuthenticatedTenant" in source
    assert "/api/health/ping" in source
