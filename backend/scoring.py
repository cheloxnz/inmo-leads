"""
InmoBot SaaS - Motor de scoring genérico basado en templates
"""
import logging

logger = logging.getLogger(__name__)


def get_nested_value(lead_dict: dict, field_path: str):
    """Obtiene valor de un campo, soporta dot notation (custom_fields.zone)"""
    parts = field_path.split(".")
    value = lead_dict
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def calculate_score(lead_dict: dict, scoring_config: dict) -> tuple:
    """
    Calcula score basado en la config del template.
    Retorna (score, status)
    """
    score = 0
    criteria = scoring_config.get("criteria", [])
    hot_threshold = scoring_config.get("hot_threshold", 7)
    warm_threshold = scoring_config.get("warm_threshold", 4)

    for criterion in criteria:
        field = criterion.get("field", "")
        points = criterion.get("points", 0)
        condition = criterion.get("condition", "not_empty")
        expected_value = criterion.get("value", "")

        actual_value = get_nested_value(lead_dict, field)

        if condition == "not_empty":
            if actual_value and str(actual_value).strip():
                score += points
        elif condition == "equals":
            if str(actual_value).lower() == str(expected_value).lower():
                score += points
        elif condition == "not_equals":
            if actual_value and str(actual_value).lower() != str(expected_value).lower():
                score += points
        elif condition == "greater_than":
            try:
                if float(actual_value) > float(expected_value):
                    score += points
            except (TypeError, ValueError):
                pass

    # Determine status
    if score >= hot_threshold:
        status = "hot"
    elif score >= warm_threshold:
        status = "warm"
    else:
        status = "cold"

    return score, status
