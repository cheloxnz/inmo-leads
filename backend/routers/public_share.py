"""Public share endpoints para Open Graph previews.

Cuando un tenant comparte una URL como:
  https://app.inmobot.com/share/{tenant_id}/{celebration_id}

LinkedIn/Twitter/WhatsApp/Slack hacen un GET y leen las meta tags OG.
La meta og:image apunta a:
  https://app.inmobot.com/api/public/share/{tenant_id}/{celebration_id}.png

Este router NO requiere auth (publico). Cacheado agresivamente (ETag + max-age).
"""
import hashlib
import io
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from PIL import Image, ImageDraw, ImageFont

from auth_routes import get_db
from cache_util import ttl_cache_get, ttl_cache_set

logger = logging.getLogger(__name__)
router = APIRouter(tags=["public-share"])

CARD_W, CARD_H = 1200, 630
DEFAULT_PRIMARY = "#3b82f6"
DEFAULT_ACCENT = "#8b5cf6"

FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

PNG_CACHE_TTL = 3600  # 1 hora in-memory; cliente cachea via headers


# ---------------- helpers ----------------

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = (hex_color or "").lstrip("#").strip()
    if len(h) != 6:
        return (59, 130, 246)
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (59, 130, 246)


def _interp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _draw_gradient(img: Image.Image, c1, c2):
    """Gradient diagonal de c1 (top-left) a c2 (bottom-right)."""
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            t = (x + y) / (w + h)
            px[x, y] = (*_interp(c1, c2, t), 255)


def _wrap_text(draw, text, font, max_w):
    """Wrappea texto en lineas para que cada una entre en max_w."""
    words = (text or "").split()
    lines = []
    cur = ""
    for w in words:
        test = (cur + " " + w).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if (bbox[2] - bbox[0]) > max_w and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def _strip_emoji(text: str) -> str:
    """Pillow + LiberationSans no tienen glyphs para emoji.
    Quitamos emoji unicode (planos > BMP) para evitar tofu boxes."""
    if not text:
        return ""
    return re.sub(r"[\U00010000-\U0010FFFF]", "", text).strip()


def _render_card(card_data: dict) -> bytes:
    """Renderiza la card como PNG bytes (1200x630)."""
    primary = _hex_to_rgb(card_data.get("primary_color") or DEFAULT_PRIMARY)
    accent = _hex_to_rgb(card_data.get("accent_color") or DEFAULT_ACCENT)

    img = Image.new("RGB", (CARD_W, CARD_H), color=primary)
    _draw_gradient(img, primary, accent)
    draw = ImageDraw.Draw(img)

    # Card blanca interior con padding
    PAD = 60
    R = 32
    inner = (PAD, PAD, CARD_W - PAD, CARD_H - PAD)
    draw.rounded_rectangle(inner, radius=R, fill=(255, 255, 255))

    # Fonts
    try:
        font_xl = ImageFont.truetype(FONT_BOLD, 64)
        font_lg = ImageFont.truetype(FONT_BOLD, 48)
        font_md = ImageFont.truetype(FONT_BOLD, 32)
        font_metric = ImageFont.truetype(FONT_BOLD, 96)
        font_sm = ImageFont.truetype(FONT_REG, 22)
    except Exception:
        font_xl = ImageFont.load_default()
        font_lg = ImageFont.load_default()
        font_md = ImageFont.load_default()
        font_metric = ImageFont.load_default()
        font_sm = ImageFont.load_default()

    # Pastilla de color con la inicial (sustituye al emoji)
    initial = (card_data.get("emoji_letter") or
               (card_data.get("celebration_type", "C")[:1].upper()))
    badge_x, badge_y, badge_r = PAD + 80, PAD + 110, 50
    draw.ellipse(
        (badge_x - badge_r, badge_y - badge_r, badge_x + badge_r, badge_y + badge_r),
        fill=primary,
    )
    bx0, by0, bx1, by1 = draw.textbbox((0, 0), initial, font=font_lg)
    draw.text(
        (badge_x - (bx1 - bx0) / 2, badge_y - (by1 - by0) / 2 - 8),
        initial, font=font_lg, fill=(255, 255, 255),
    )

    # Titulo (multilinea)
    title = _strip_emoji(card_data.get("title", "Logro alcanzado"))
    max_text_w = CARD_W - 2 * PAD - 120
    title_lines = _wrap_text(draw, title, font_xl, max_text_w)
    y = PAD + 200
    for ln in title_lines[:3]:
        draw.text((PAD + 60, y), ln, font=font_xl, fill=(15, 23, 42))
        y += 78

    # Metric grande si hay
    metric = card_data.get("metric")
    if metric is not None:
        draw.text(
            (PAD + 60, y + 10), str(metric),
            font=font_metric, fill=primary,
        )

    # Footer: business_name (left) + powered_by (right)
    business = _strip_emoji(card_data.get("business_name") or "Mi negocio")
    draw.text(
        (PAD + 60, CARD_H - PAD - 70),
        business[:40], font=font_md, fill=(71, 85, 105),
    )

    powered = "Hecho con InmoBot AI"
    pw_bbox = draw.textbbox((0, 0), powered, font=font_sm)
    draw.text(
        (CARD_W - PAD - 60 - (pw_bbox[2] - pw_bbox[0]), CARD_H - PAD - 50),
        powered, font=font_sm, fill=(148, 163, 184),
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


async def _fetch_card_data(db: AsyncIOMotorDatabase, tenant_id: str, celebration_id: str) -> Optional[dict]:
    cel = await db.coach_celebrations.find_one(
        {"celebration_id": celebration_id, "tenant_id": tenant_id},
        {"_id": 0},
    )
    if not cel:
        return None
    tenant = await db.tenants.find_one(
        {"tenant_id": tenant_id},
        {"_id": 0, "business_name": 1, "name": 1, "logo_url": 1,
         "primary_color": 1, "accent_color": 1},
    ) or {}
    return {
        "celebration_type": cel.get("celebration_type"),
        "title": cel.get("title"),
        "body": cel.get("body"),
        "metric": cel.get("metric"),
        "business_name": tenant.get("business_name") or tenant.get("name") or "",
        "logo_url": tenant.get("logo_url") or "",
        "primary_color": tenant.get("primary_color") or DEFAULT_PRIMARY,
        "accent_color": tenant.get("accent_color") or DEFAULT_ACCENT,
        "emoji_letter": (cel.get("celebration_type") or "C")[:1].upper(),
    }


def _etag_for(data: dict) -> str:
    """ETag estable basado en titulo+metric+colors+business."""
    payload = "|".join(str(data.get(k, "")) for k in (
        "title", "metric", "business_name", "primary_color", "accent_color"
    ))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def _public_base_url(request: Request) -> str:
    """Devuelve la URL publica base. Prioriza:
    1. PUBLIC_BASE_URL del env (override explicito)
    2. X-Forwarded-Proto + X-Forwarded-Host (reverse proxy estandar)
    3. request.base_url (fallback)
    """
    import os as _os
    env_url = _os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if env_url:
        return env_url

    fwd_host = request.headers.get("x-forwarded-host") or request.headers.get("x-original-host")
    fwd_proto = request.headers.get("x-forwarded-proto") or request.headers.get("x-original-proto")
    if fwd_host:
        proto = fwd_proto or "https"
        # x-forwarded-host puede traer multiple hosts separados por coma; agarrar el primero
        host = fwd_host.split(",")[0].strip()
        return f"{proto}://{host}"

    return str(request.base_url).rstrip("/")


def _escape_html(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ---------------- endpoints ----------------

async def _bump_counter(db, tenant_id: str, celebration_id: str, field: str):
    """Best-effort, no bloquea response. Usado via BackgroundTasks."""
    try:
        await db.coach_celebrations.update_one(
            {"celebration_id": celebration_id, "tenant_id": tenant_id},
            {"$inc": {f"shares.{field}": 1}},
        )
    except Exception:
        pass


@router.get("/public/share/{tenant_id}/{celebration_id}.png")
async def share_card_png(
    tenant_id: str,
    celebration_id: str,
    request: Request,
    background: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """PNG renderizada de la celebracion. Publica, cacheada agresivamente con ETag.
    Incrementa shares.preview_views (background task, no bloquea response)."""
    cache_key = f"{tenant_id}/{celebration_id}"
    cached = ttl_cache_get("share_png", cache_key)
    if cached is None:
        data = await _fetch_card_data(db, tenant_id, celebration_id)
        if not data:
            raise HTTPException(status_code=404, detail="Celebration no encontrada")
        png_bytes = _render_card(data)
        etag = _etag_for(data)
        cached = (png_bytes, etag)
        ttl_cache_set("share_png", cache_key, cached, ttl=PNG_CACHE_TTL)
    png_bytes, etag = cached

    # Conditional GET (304 Not Modified)
    inm = request.headers.get("if-none-match")
    if inm and etag in inm:
        return Response(status_code=304, headers={"ETag": f'"{etag}"'})

    # Tracking en background (no bloquea el response)
    background.add_task(_bump_counter, db, tenant_id, celebration_id, "preview_views")

    headers = {
        "ETag": f'"{etag}"',
        "Cache-Control": "public, max-age=3600, s-maxage=86400",
        "Content-Type": "image/png",
    }
    return StreamingResponse(io.BytesIO(png_bytes), media_type="image/png", headers=headers)


@router.get("/public/share/{tenant_id}/{celebration_id}", response_class=HTMLResponse)
async def share_html_page(
    tenant_id: str,
    celebration_id: str,
    request: Request,
    background: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Pagina HTML con meta tags Open Graph + Twitter Card.
    Cuando se comparte la URL, LinkedIn/X/WhatsApp/Slack/Discord crawlean este HTML
    y previsualizan automaticamente la imagen + titulo.

    INCLUYE: mini formulario de captura de lead con attribution al tenant referrer.
    Cada celebracion compartida se vuelve un canal de adquisicion trackeable.
    """
    data = await _fetch_card_data(db, tenant_id, celebration_id)
    if not data:
        raise HTTPException(status_code=404, detail="Celebration no encontrada")

    base = _public_base_url(request)
    image_url = f"{base}/api/public/share/{tenant_id}/{celebration_id}.png"
    page_url = f"{base}/api/public/share/{tenant_id}/{celebration_id}"
    # URL del wizard de signup con attribution
    signup_url = f"{base}/signup?ref={tenant_id}&ref_celebration_id={celebration_id}"
    # URL del endpoint de captura (POST)
    capture_url = f"{base}/api/public/share/{tenant_id}/{celebration_id}/lead"

    title = _escape_html(_strip_emoji(data.get("title") or "Logro alcanzado"))
    body = _escape_html(_strip_emoji(data.get("body") or ""))
    business = _escape_html(_strip_emoji(data.get("business_name") or "Mi negocio"))
    description = body or f"{business} alcanzó un nuevo logro con InmoBot AI"
    primary = _escape_html(data.get("primary_color") or DEFAULT_PRIMARY)

    background.add_task(_bump_counter, db, tenant_id, celebration_id, "html_views")

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} · {business}</title>
  <meta name="description" content="{description}">

  <!-- Open Graph -->
  <meta property="og:type" content="website">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:image" content="{image_url}">
  <meta property="og:image:secure_url" content="{image_url}">
  <meta property="og:image:width" content="{CARD_W}">
  <meta property="og:image:height" content="{CARD_H}">
  <meta property="og:image:type" content="image/png">
  <meta property="og:url" content="{page_url}">
  <meta property="og:site_name" content="InmoBot AI">

  <!-- Twitter / X -->
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{description}">
  <meta name="twitter:image" content="{image_url}">

  <meta property="article:author" content="{business}">

  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:system-ui,-apple-system,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:32px;text-align:center}}
    .card{{max-width:720px;width:100%;background:#1e293b;border-radius:16px;padding:48px;box-shadow:0 20px 60px rgba(0,0,0,0.4);border:1px solid #334155}}
    img{{width:100%;height:auto;border-radius:12px;display:block;margin:0 auto 24px;box-shadow:0 10px 40px rgba(0,0,0,0.3)}}
    h1{{font-size:1.75rem;font-weight:bold;margin-bottom:12px;color:#fff}}
    p{{font-size:1rem;line-height:1.5;color:#94a3b8;margin-bottom:24px}}
    .lead-box{{margin-top:32px;padding:24px;background:rgba({_hex_to_rgb(primary)[0]},{_hex_to_rgb(primary)[1]},{_hex_to_rgb(primary)[2]},0.08);border-radius:12px;border:1px solid rgba({_hex_to_rgb(primary)[0]},{_hex_to_rgb(primary)[1]},{_hex_to_rgb(primary)[2]},0.3)}}
    .lead-box h2{{font-size:1.25rem;color:#fff;margin-bottom:8px}}
    .lead-box .sub{{font-size:0.875rem;color:#94a3b8;margin-bottom:20px}}
    .lead-form{{display:flex;flex-wrap:wrap;gap:8px;justify-content:center}}
    .lead-form input{{flex:1;min-width:200px;padding:12px 16px;border-radius:9999px;border:1px solid #475569;background:#0f172a;color:#fff;font-size:0.95rem}}
    .lead-form input:focus{{outline:none;border-color:{primary}}}
    .lead-form button{{padding:12px 24px;background:{primary};color:#fff;border:none;border-radius:9999px;font-weight:600;font-size:0.95rem;cursor:pointer;transition:opacity 0.2s}}
    .lead-form button:hover{{opacity:0.85}}
    .lead-form button:disabled{{opacity:0.4;cursor:not-allowed}}
    .lead-success{{padding:16px;background:rgba(16,185,129,0.15);border:1px solid #10b981;border-radius:8px;color:#a7f3d0;margin-top:12px;display:none}}
    .lead-error{{padding:12px;background:rgba(239,68,68,0.15);border:1px solid #ef4444;border-radius:8px;color:#fecaca;margin-top:12px;display:none;font-size:0.875rem}}
    a.cta{{display:inline-block;padding:12px 28px;background:{primary};color:#fff;text-decoration:none;border-radius:9999px;font-weight:600;transition:opacity 0.2s}}
    a.cta:hover{{opacity:0.85}}
    a.secondary{{display:block;margin-top:16px;color:#94a3b8;font-size:0.875rem;text-decoration:underline}}
    footer{{margin-top:32px;font-size:0.75rem;color:#64748b}}
    .ref-badge{{display:inline-flex;align-items:center;gap:6px;padding:4px 12px;background:rgba(245,158,11,0.15);border:1px solid #f59e0b;border-radius:9999px;color:#fbbf24;font-size:0.7rem;margin-bottom:16px}}
  </style>
</head>
<body>
  <div class="card">
    <img src="{image_url}" alt="{title}">
    <h1>{title}</h1>
    <p>{description}</p>

    <div class="lead-box">
      <span class="ref-badge">✦ Te trajo {business}</span>
      <h2>¿Querés un bot así para tu negocio?</h2>
      <p class="sub">Probalo gratis 14 días. Sin tarjeta. Setup en 5 minutos.</p>

      <form class="lead-form" id="lf" onsubmit="return submitLead(event)">
        <input type="email" id="email" placeholder="tu@email.com" required autocomplete="email">
        <button type="submit" id="btn">Quiero mi bot →</button>
      </form>
      <div class="lead-success" id="ok">
        ✓ ¡Listo! Te enviamos info por email. <a href="{signup_url}" class="cta" style="margin-top:12px">Continuar registro completo</a>
      </div>
      <div class="lead-error" id="err"></div>

      <a href="{signup_url}" class="secondary" target="_blank" rel="noopener">o registrate completo ahora →</a>
    </div>
  </div>
  <footer>Hecho con InmoBot AI · {business}</footer>

  <script>
    async function submitLead(e) {{
      e.preventDefault();
      const email = document.getElementById('email').value.trim();
      const btn = document.getElementById('btn');
      const ok = document.getElementById('ok');
      const err = document.getElementById('err');
      err.style.display = 'none';
      ok.style.display = 'none';
      btn.disabled = true;
      btn.textContent = 'Enviando...';
      try {{
        const r = await fetch('{capture_url}', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ email }}),
        }});
        const data = await r.json();
        if (!r.ok) {{
          err.textContent = data.detail || 'Error al guardar el email';
          err.style.display = 'block';
          btn.disabled = false;
          btn.textContent = 'Quiero mi bot →';
          return false;
        }}
        document.getElementById('lf').style.display = 'none';
        ok.style.display = 'block';
      }} catch (ex) {{
        err.textContent = 'Error de red, probá de nuevo';
        err.style.display = 'block';
        btn.disabled = false;
        btn.textContent = 'Quiero mi bot →';
      }}
      return false;
    }}
  </script>
</body>
</html>
"""
    return HTMLResponse(
        content=html,
        headers={"Cache-Control": "public, max-age=600, s-maxage=3600"},
    )


# ---------------- Lead capture endpoint ----------------

@router.post("/public/share/{tenant_id}/{celebration_id}/lead")
async def capture_referral_lead(
    tenant_id: str,
    celebration_id: str,
    body: dict,
    request: Request,
    background: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Captura email de visitante interesado. Trackea attribution al referrer.
    Idempotente entre intentos NO convertidos: mismo email + ref + sin convertir = upsert.
    Si el lead ya convirtio (signup completo), un nuevo submit del form crea un lead nuevo
    (intencional: representa que el visitante volvio a la URL post-signup; util para retargeting).
    """
    email = ((body or {}).get("email") or "").strip().lower()
    if not email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=400, detail="Email invalido")
    if len(email) > 200:
        raise HTTPException(status_code=400, detail="Email demasiado largo")

    # Validar que la celebration existe (anti-abuse: solo emails desde URLs reales)
    cel = await db.coach_celebrations.find_one(
        {"celebration_id": celebration_id, "tenant_id": tenant_id},
        {"_id": 1},
    )
    if not cel:
        raise HTTPException(status_code=404, detail="Celebration no encontrada")

    # Si el email ya es un agent registrado, NO crear lead (no sentido)
    existing_agent = await db.agents.find_one({"email": email}, {"_id": 1, "tenant_id": 1})
    if existing_agent:
        return {
            "captured": False,
            "reason": "already_registered",
            "message": "Ese email ya tiene cuenta. Iniciá sesión.",
        }

    now = datetime.now(timezone.utc)
    ip = request.client.host if request.client else None
    ua = (request.headers.get("user-agent") or "")[:300]

    # Upsert: mismo email + mismo ref + sin convertir = no duplicar
    res = await db.referral_leads.update_one(
        {"ref_tenant_id": tenant_id, "email": email, "converted_tenant_id": None},
        {
            "$setOnInsert": {
                "lead_id": __import__("uuid").uuid4().hex,
                "ref_tenant_id": tenant_id,
                "ref_celebration_id": celebration_id,
                "email": email,
                "ip": ip,
                "user_agent": ua,
                "created_at": now,
                "converted_tenant_id": None,
                "converted_at": None,
            },
            "$set": {"last_seen_at": now},
            "$inc": {"submission_count": 1},
        },
        upsert=True,
    )

    is_new = res.upserted_id is not None

    # Bump counters del referrer (background)
    background.add_task(_bump_referral_counter, db, tenant_id, "leads" if is_new else "leads_repeat")

    return {
        "captured": True,
        "is_new": is_new,
        "message": "¡Listo! Te enviamos info por email." if is_new else "Ya tenemos tu email registrado.",
    }


async def _bump_referral_counter(db, tenant_id: str, field: str):
    """Best-effort, background."""
    try:
        await db.tenants.update_one(
            {"tenant_id": tenant_id},
            {"$inc": {f"referral_stats.{field}": 1}},
        )
    except Exception:
        pass
