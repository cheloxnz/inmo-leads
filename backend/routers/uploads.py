"""Router de upload de archivos (logos, imagenes de productos)"""
import os
import uuid
import mimetypes
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request

from auth_routes import require_admin, get_db
from models import User

router = APIRouter(tags=["uploads"])

# Storage path
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/app/backend/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
(UPLOAD_DIR / "logos").mkdir(exist_ok=True)
(UPLOAD_DIR / "products").mkdir(exist_ok=True)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/svg+xml", "image/gif"}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB


@router.post("/uploads/logo")
async def upload_logo(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
):
    """Admin: sube un logo y devuelve la URL publica.
    Lee el archivo en chunks abortando temprano si excede MAX_FILE_SIZE.
    """
    # Validar tipo (antes de leer body para no malgastar memoria)
    content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0]
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo no permitido: {content_type}. Permitidos: jpg, png, webp, svg, gif."
        )

    # Lectura streaming en chunks de 64KB; abortar si supera MAX_FILE_SIZE
    chunks = []
    total = 0
    chunk_size = 64 * 1024
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="Archivo demasiado grande (max 2 MB)")
        chunks.append(chunk)

    if total == 0:
        raise HTTPException(status_code=400, detail="Archivo vacio")

    content = b"".join(chunks)

    # Extension segura
    ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/svg+xml": ".svg",
        "image/gif": ".gif",
    }
    ext = ext_map.get(content_type, ".bin")
    filename = f"{current_user.tenant_id}_{uuid.uuid4().hex}{ext}"
    path = UPLOAD_DIR / "logos" / filename
    with open(path, "wb") as f:
        f.write(content)

    # Construir URL publica respetando proxy
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.url.hostname
    if request.url.port and request.url.port not in (80, 443):
        host = f"{host}:{request.url.port}"
    public_url = f"{scheme}://{host}/api/uploads/logos/{filename}"

    return {
        "url": public_url,
        "filename": filename,
        "size_bytes": total,
        "content_type": content_type,
    }


@router.get("/uploads/logos/{filename}")
async def serve_logo(filename: str):
    """Sirve un logo subido. Validacion de path traversal."""
    from fastapi.responses import FileResponse
    # Validar filename: solo alfanumerico + - _ + extension
    import re
    if not re.match(r"^[a-zA-Z0-9_\-]+\.(jpg|png|webp|svg|gif)$", filename):
        raise HTTPException(status_code=400, detail="Filename invalido")
    path = UPLOAD_DIR / "logos" / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="No encontrado")
    # Verificar que el path resuelto sigue dentro del directorio
    if not str(path.resolve()).startswith(str((UPLOAD_DIR / "logos").resolve())):
        raise HTTPException(status_code=400, detail="Path invalido")
    return FileResponse(path)
