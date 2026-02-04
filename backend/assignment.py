import logging
from typing import Optional, List
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from models import LeadStatus
import random

logger = logging.getLogger(__name__)

class AssignmentEngine:
    """Motor de asignación automática de leads a asesores"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
    
    async def assign_lead_to_agent(self, lead_phone: str, lead_data: dict) -> Optional[str]:
        """Asigna lead a asesor usando algoritmo híbrido"""
        try:
            intent = lead_data.get('intent')
            zone = lead_data.get('zone', '').lower()
            
            # Paso 1: Obtener asesores activos
            agents = await self.db.agents.find(
                {"active": True},
                {"_id": 0}
            ).to_list(100)
            
            if not agents:
                logger.warning("No hay asesores activos para asignar")
                return None
            
            # Paso 2: Filtrar por especialidad
            compatible_agents = []
            for agent in agents:
                specialties = agent.get('specialties', [])
                if not specialties or intent in specialties or 'ambos' in specialties:
                    compatible_agents.append(agent)
            
            if not compatible_agents:
                compatible_agents = agents
            
            # Paso 3: Filtrar por zona (si configurado)
            if zone:
                zone_agents = []
                for agent in compatible_agents:
                    agent_zones = [z.lower() for z in agent.get('zones', [])]
                    if not agent_zones or zone in ' '.join(agent_zones):
                        zone_agents.append(agent)
                
                if zone_agents:
                    compatible_agents = zone_agents
            
            # Paso 4: Contar leads activos por asesor
            agent_loads = {}
            for agent in compatible_agents:
                count = await self.db.leads.count_documents({
                    "assigned_agent": agent['email'],
                    "status": {"$in": ["hot", "warm"]}
                })
                agent_loads[agent['email']] = {
                    "agent": agent,
                    "load": count
                }
            
            # Paso 5: Asignar al que tiene menos carga
            if agent_loads:
                min_load_agent = min(agent_loads.values(), key=lambda x: x['load'])
                selected_agent = min_load_agent['agent']
                
                # Actualizar lead con asesor asignado
                await self.db.leads.update_one(
                    {"phone": lead_phone},
                    {
                        "$set": {
                            "assigned_agent": selected_agent['email'],
                            "assigned_agent_name": selected_agent['name'],
                            "assigned_at": datetime.utcnow().isoformat()
                        }
                    }
                )
                
                logger.info(f"Lead {lead_phone} asignado a {selected_agent['name']} (carga: {min_load_agent['load']} leads)")
                return selected_agent['email']
            
            return None
        
        except Exception as e:
            logger.error(f"Error asignando lead: {str(e)}")
            return None
    
    async def get_agent_metrics(self, agent_email: str) -> dict:
        """Obtiene métricas de un asesor"""
        try:
            total_assigned = await self.db.leads.count_documents({"assigned_agent": agent_email})
            active_leads = await self.db.leads.count_documents({
                "assigned_agent": agent_email,
                "status": {"$in": ["hot", "warm"]}
            })
            cold_leads = await self.db.leads.count_documents({
                "assigned_agent": agent_email,
                "status": "cold"
            })
            
            # Leads con cita
            with_appointment = await self.db.leads.count_documents({
                "assigned_agent": agent_email,
                "appointment_datetime": {"$exists": True, "$ne": None}
            })
            
            # Score promedio de sus leads
            pipeline = [
                {"$match": {"assigned_agent": agent_email}},
                {"$group": {"_id": None, "avg_score": {"$avg": "$score"}}}
            ]
            avg_result = await self.db.leads.aggregate(pipeline).to_list(1)
            avg_score = avg_result[0]["avg_score"] if avg_result else 0
            
            return {
                "total_assigned": total_assigned,
                "active_leads": active_leads,
                "cold_leads": cold_leads,
                "with_appointment": with_appointment,
                "avg_score": round(avg_score, 2),
                "conversion_rate": round((with_appointment / total_assigned * 100) if total_assigned > 0 else 0, 2)
            }
        
        except Exception as e:
            logger.error(f"Error obteniendo métricas de asesor: {str(e)}")
            return {}

from datetime import datetime