"""Router de widget analytics + widget.js drop-in"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from auth_routes import get_current_user, require_admin, get_db
from widget_analytics_service import WidgetAnalyticsService
from models import User

router = APIRouter(tags=["widget"])

_db = get_db()
widget_service = WidgetAnalyticsService(_db)


@router.post("/public/catalog/{tenant_id}/track")
async def track_widget_event(tenant_id: str, request: Request, body: dict):
    """Registra un evento del widget publico. Sin auth - llamado desde la pagina publica."""
    event_type = (body or {}).get("event_type", "")
    if not event_type:
        raise HTTPException(status_code=400, detail="event_type requerido")

    # Validar que el tenant exista
    tenant = await _db.tenants.find_one({"tenant_id": tenant_id, "active": True}, {"_id": 0, "tenant_id": 1})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "").split(",")[0].strip()
    user_agent = request.headers.get("user-agent", "")
    referrer = request.headers.get("referer", "") or (body or {}).get("referrer", "")

    return await widget_service.track_event(
        tenant_id=tenant_id,
        event_type=event_type,
        product_id=(body or {}).get("product_id"),
        query=(body or {}).get("query"),
        referrer=referrer,
        user_agent=user_agent,
        client_ip=client_ip,
        session_id=(body or {}).get("session_id"),
    )


@router.get("/widget/analytics")
async def get_widget_analytics(days: int = 30, current_user: User = Depends(require_admin)):
    """Admin: retorna metricas del widget del tenant"""
    return await widget_service.get_analytics(current_user.tenant_id, days=days)


@router.get("/superadmin/widget/analytics")
async def get_global_widget_analytics(current_user: User = Depends(get_current_user)):
    """SuperAdmin: metricas globales del widget por tenant"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Solo superadmin")
    return await widget_service.get_global_analytics()


@router.get("/public/catalog/{tenant_id}/widget.js")
async def get_widget_js(tenant_id: str, request: Request):
    """Devuelve un script JS drop-in para incrustar el widget en cualquier sitio.

    Uso:
      <div id="inmobot-catalog"></div>
      <script src="https://.../api/public/catalog/<tenant_id>/widget.js"></script>
    """
    # Construir la URL base del widget desde el host del request (respetando proxy)
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.url.hostname
    if request.url.port and request.url.port not in (80, 443):
        host = f"{host}:{request.url.port}"
    widget_url = f"{scheme}://{host}/p/catalogo/{tenant_id}?embed=1"

    js_code = f"""
(function() {{
  var TENANT_ID = {tenant_id!r};
  var WIDGET_URL = {widget_url!r};
  var container = document.getElementById('inmobot-catalog') || (function() {{
    var d = document.createElement('div');
    d.id = 'inmobot-catalog';
    document.currentScript && document.currentScript.parentNode.insertBefore(d, document.currentScript);
    return d;
  }})();

  var iframe = document.createElement('iframe');
  iframe.src = WIDGET_URL;
  iframe.style.width = '100%';
  iframe.style.minHeight = '600px';
  iframe.style.border = '0';
  iframe.style.borderRadius = '12px';
  iframe.loading = 'lazy';
  iframe.title = 'Catalogo InmoBot';
  iframe.setAttribute('data-tenant', TENANT_ID);
  container.appendChild(iframe);

  // Auto-resize iframe cuando cambia contenido (si el widget emite mensajes)
  window.addEventListener('message', function(e) {{
    try {{
      if (e.data && e.data.type === 'inmobot-resize' && e.data.tenant === TENANT_ID) {{
        iframe.style.height = e.data.height + 'px';
      }}
    }} catch (err) {{}}
  }});
}})();
""".strip()

    return Response(
        content=js_code,
        media_type="application/javascript; charset=utf-8",
        headers={
            "Cache-Control": "public, max-age=300",
            "Access-Control-Allow-Origin": "*",
        }
    )
