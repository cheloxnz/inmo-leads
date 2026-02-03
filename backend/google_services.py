import os
import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class GoogleSheetsService:
    """Servicio para sincronizar leads con Google Sheets como CRM"""
    
    def __init__(self):
        self.credentials_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
        self.client = None
        self.spreadsheet = None
        
        if self.credentials_json:
            try:
                import gspread
                from google.oauth2.service_account import Credentials
                
                creds_dict = json.loads(self.credentials_json)
                scopes = [
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
                
                creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
                self.client = gspread.authorize(creds)
                logger.info("Google Sheets client inicializado")
            except Exception as e:
                logger.error(f"Error inicializando Google Sheets: {e}")
    
    def set_spreadsheet(self, spreadsheet_url_or_id: str):
        """Configura la hoja de cálculo a usar"""
        if not self.client:
            logger.warning("Google Sheets client no inicializado")
            return
        
        try:
            self.spreadsheet = self.client.open_by_url(spreadsheet_url_or_id)
            logger.info(f"Spreadsheet configurada: {self.spreadsheet.title}")
        except:
            try:
                self.spreadsheet = self.client.open_by_key(spreadsheet_url_or_id)
                logger.info(f"Spreadsheet configurada: {self.spreadsheet.title}")
            except Exception as e:
                logger.error(f"Error abriendo spreadsheet: {e}")
    
    async def sync_lead_to_sheet(self, lead: Dict) -> bool:
        """Sincroniza un lead a Google Sheets"""
        if not self.spreadsheet:
            logger.warning("Spreadsheet no configurada")
            return False
        
        try:
            worksheet = self.spreadsheet.worksheet("Leads")
        except:
            worksheet = self.spreadsheet.add_worksheet("Leads", rows=1000, cols=20)
            headers = [
                "Teléfono", "Nombre", "Estado Flujo", "Intención", "Zona", 
                "Presupuesto", "Tipo Propiedad", "Dormitorios", "Requisitos",
                "Urgencia", "Financiamiento", "Score", "Clasificación",
                "Fecha Cita", "Asesor Asignado", "Fuente", "Fecha Creación", "Notas"
            ]
            worksheet.append_row(headers)
        
        row_data = [
            lead.get("phone", ""),
            lead.get("name", ""),
            lead.get("flow_stage", ""),
            lead.get("intent", ""),
            lead.get("zone", ""),
            lead.get("budget_text", ""),
            lead.get("property_type", ""),
            str(lead.get("bedrooms", "")),
            ", ".join(lead.get("must_have", [])),
            lead.get("urgency", ""),
            lead.get("financing", ""),
            str(lead.get("score", 0)),
            lead.get("status", ""),
            lead.get("appointment_datetime", ""),
            lead.get("assigned_agent", ""),
            lead.get("source", ""),
            lead.get("created_at", ""),
            lead.get("notes", "")
        ]
        
        try:
            cell = worksheet.find(lead["phone"])
            worksheet.update(f"A{cell.row}:R{cell.row}", [row_data])
            logger.info(f"Lead {lead['phone']} actualizado en Sheets")
        except:
            worksheet.append_row(row_data)
            logger.info(f"Lead {lead['phone']} agregado a Sheets")
        
        return True

class GoogleCalendarService:
    """Servicio para crear eventos en Google Calendar"""
    
    def __init__(self):
        self.credentials_json = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_JSON")
        self.service = None
        
        if self.credentials_json:
            try:
                from google.oauth2.service_account import Credentials
                from googleapiclient.discovery import build
                
                creds_dict = json.loads(self.credentials_json)
                scopes = ['https://www.googleapis.com/auth/calendar']
                
                creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
                self.service = build('calendar', 'v3', credentials=creds)
                logger.info("Google Calendar service inicializado")
            except Exception as e:
                logger.error(f"Error inicializando Google Calendar: {e}")
    
    async def create_appointment(self, lead_name: str, lead_phone: str, appointment_datetime: datetime, duration_minutes: int = 60) -> Optional[str]:
        """Crea un evento en Google Calendar"""
        if not self.service:
            logger.warning("Google Calendar service no inicializado")
            return None
        
        try:
            end_time = appointment_datetime + timedelta(minutes=duration_minutes)
            
            event = {
                'summary': f'Visita - {lead_name}',
                'description': f'Cliente: {lead_name}\nTeléfono: {lead_phone}\nAgendado por WhatsApp Bot',
                'start': {
                    'dateTime': appointment_datetime.isoformat(),
                    'timeZone': 'America/Argentina/Buenos_Aires',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'America/Argentina/Buenos_Aires',
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},
                        {'method': 'popup', 'minutes': 30},
                    ],
                },
            }
            
            created_event = self.service.events().insert(calendarId='primary', body=event).execute()
            logger.info(f"Evento creado en Calendar: {created_event.get('id')}")
            return created_event.get('htmlLink')
        
        except Exception as e:
            logger.error(f"Error creando evento en Calendar: {e}")
            return None