from models import Lead, LeadStatus, UrgencyLevel, FinancingType, LeadIntent, FlowStage
import logging

logger = logging.getLogger(__name__)

class ScoringEngine:
    """Motor de scoring para calificación de leads"""
    
    @staticmethod
    def calculate_score(lead: Lead) -> int:
        """Calcula el score del lead basado en sus respuestas"""
        score = 0
        
        # Presupuesto definido: +2
        if lead.budget_text:
            score += 2
            logger.info(f"Lead {lead.phone}: +2 puntos por presupuesto definido")
        
        # Zona definida: +2
        if lead.zone:
            score += 2
            logger.info(f"Lead {lead.phone}: +2 puntos por zona definida")
        
        # Tipo de propiedad definido: +1
        if lead.property_type:
            score += 1
            logger.info(f"Lead {lead.phone}: +1 punto por tipo de propiedad")
        
        # Urgencia alta: +3
        if lead.urgency == UrgencyLevel.URGENTE:
            score += 3
            logger.info(f"Lead {lead.phone}: +3 puntos por urgencia alta")
        elif lead.urgency == UrgencyLevel.PROXIMO_MES:
            score += 2
            logger.info(f"Lead {lead.phone}: +2 puntos por urgencia media")
        elif lead.urgency == UrgencyLevel.MESES:
            score += 1
            logger.info(f"Lead {lead.phone}: +1 punto por urgencia baja")
        elif lead.urgency == UrgencyLevel.SOLO_MIRANDO:
            score += 0
            logger.info(f"Lead {lead.phone}: 0 puntos - solo mirando")
        
        # Financiamiento definido: +1
        if lead.financing and lead.financing != FinancingType.NO_SE:
            score += 1
            logger.info(f"Lead {lead.phone}: +1 punto por financiamiento definido")
        
        # Intención de compra (vs alquiler): +1
        if lead.intent == LeadIntent.COMPRAR:
            score += 1
            logger.info(f"Lead {lead.phone}: +1 punto por intención de compra")
        
        # Tiene requisitos específicos: +1
        if lead.must_have and len(lead.must_have) > 0:
            score += 1
            logger.info(f"Lead {lead.phone}: +1 punto por requisitos específicos")
        
        logger.info(f"Lead {lead.phone}: Score total = {score}")
        return score
    
    @staticmethod
    def classify_lead(score: int) -> LeadStatus:
        """Clasifica el lead según su score"""
        if score >= 7:
            return LeadStatus.HOT
        elif score >= 4:
            return LeadStatus.WARM
        else:
            return LeadStatus.COLD
    
    @staticmethod
    def should_handoff_to_human(lead: Lead) -> bool:
        """Determina si el lead debe pasar a asesor humano"""
        # Lead caliente (score >= 7)
        if lead.score >= 7:
            logger.info(f"Handoff: Lead {lead.phone} tiene score alto ({lead.score})")
            return True
        
        # Ha llegado al final del flujo y acepto agendar
        if lead.flow_stage in [FlowStage.CONFIRMATION, FlowStage.HANDOFF]:
            logger.info(f"Handoff: Lead {lead.phone} completó flujo")
            return True
        
        # Tiene cita agendada
        if lead.appointment_datetime:
            logger.info(f"Handoff: Lead {lead.phone} tiene cita agendada")
            return True
        
        return False