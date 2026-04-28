"""Router de templates publicos por rubro"""
from fastapi import APIRouter, HTTPException
from flow_templates import get_all_templates, get_template

router = APIRouter(tags=["templates"])


@router.get("/templates")
async def list_templates():
    """Lista todos los templates de rubro disponibles (publico)"""
    return get_all_templates()


@router.get("/templates/{template_id}")
async def get_template_detail(template_id: str):
    """Obtiene detalle de un template"""
    template = get_template(template_id)
    if template["id"] != template_id and template_id != "servicios":
        raise HTTPException(status_code=404, detail="Template no encontrado")
    return template
