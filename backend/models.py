from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum

class LeadIntent(str, Enum):
    COMPRAR = "comprar"
    ALQUILAR = "alquilar"
    VENDER = "vender"
    INVERSION = "inversion"
    SIN_DEFINIR = "sin_definir"

class PropertyType(str, Enum):
    DEPARTAMENTO = "departamento"
    CASA = "casa"
    PH = "ph"
    LOCAL = "local"
    TERRENO = "terreno"
    OFICINA = "oficina"
    OTRO = "otro"

class LeadStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    APPOINTMENT = "appointment"
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class FlowStage(str, Enum):
    WELCOME = "welcome"
    INTENT = "intent"
    NAME = "name"
    ZONE = "zone"
    BUDGET = "budget"
    PROPERTY_TYPE = "property_type"
    BEDROOMS = "bedrooms"
    MUST_HAVE = "must_have"
    URGENCY = "urgency"
    FINANCING = "financing"
    SCORING = "scoring"
    APPOINTMENT_OFFER = "appointment_offer"
    SELECT_DAY = "select_day"
    SELECT_TIME = "select_time"
    CONFIRMATION = "confirmation"
    HANDOFF = "handoff"
    COMPLETED = "completed"
    DISQUALIFIED = "disqualified"
    RESCHEDULE_CONFIRM = "reschedule_confirm"
    RESCHEDULE_DAY = "reschedule_day"
    RESCHEDULE_TIME = "reschedule_time"
    CANCEL_CONFIRM = "cancel_confirm"
    CONSULTING = "consulting"
    SCHEDULE_DAY = "schedule_day"

class UrgencyLevel(str, Enum):
    URGENTE = "urgente"
    PROXIMO_MES = "proximo_mes"
    MESES = "meses"
    SOLO_MIRANDO = "solo_mirando"

class FinancingType(str, Enum):
    EFECTIVO = "efectivo"
    CREDITO_HIPOTECARIO = "credito_hipotecario"
    CREDITO_UVA = "credito_uva"
    PROCREAR = "procrear"
    MIXTO = "mixto"
    NO_SE = "no_se"

class EmailType(str, Enum):
    HOT_LEAD = "hot_lead"
    APPOINTMENT_REMINDER = "appointment_reminder"
    WARM_LEAD_REACTIVATION = "warm_lead_reactivation"
    NEW_REFERRAL_COMMISSION = "new_referral_commission"
    TRIAL_ENDING_SOON = "trial_ending_soon"
    WEEKLY_DIGEST = "weekly_digest"
    WELCOME_TENANT = "welcome_tenant"
    UPSELL_UNMET_DEMAND = "upsell_unmet_demand"
    WAITLIST_THRESHOLD_ALERT = "waitlist_threshold_alert"
    TEST = "test"


# ============================================
# MULTI-TENANT: Tenant Model
# ============================================

class Tenant(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tenant_id: str  # unique slug (ej: "inmobiliaria-lopez")
    name: str  # "Inmobiliaria López"
    plan: str = "basic"  # basic, pro, enterprise
    template_id: str = "servicios"  # inmobiliaria, clinica, restaurante, servicios, ecommerce
    active: bool = True
    # WhatsApp config per tenant
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_business_account_id: str = ""
    webhook_verify_token: str = ""
    # Limits
    max_leads: int = 2000
    max_agents: int = 10
    max_ai_messages: int = 2000
    # AI Config (optional own key)
    openai_api_key: str = ""  # If empty, uses platform key
    # Subscription
    subscription_status: str = "active"  # active, trial, suspended, cancelled
    subscription_plan: str = "basic"
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    # Contact
    contact_email: str = ""
    contact_phone: str = ""
    country: str = ""
    # Branding
    business_name: str = ""
    business_tagline: str = ""
    # Feature flags por tenant (override del plan; valor truthy/falsy o objeto config)
    features: dict = Field(default_factory=dict)
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class TenantCreate(BaseModel):
    tenant_id: str
    name: str
    contact_email: str
    contact_phone: str = ""
    country: str = ""
    plan: str = "basic"
    admin_email: str
    admin_password: str
    admin_name: str = "Administrador"


# ============================================
# Lead Models (with tenant_id)
# ============================================

class Lead(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tenant_id: str = ""
    phone: str
    name: Optional[str] = None
    flow_stage: str = "welcome"
    current_step_index: int = 0  # Index in the template flow_steps
    intent: Optional[str] = None
    urgency: Optional[str] = None
    custom_fields: dict = Field(default_factory=dict)  # Generic fields defined by template
    score: int = 0
    status: str = "cold"
    appointment_type: Optional[str] = None
    appointment_datetime: Optional[datetime] = None
    appointment_reminder_sent: bool = False
    is_urgent: bool = False
    tags: List[str] = []
    assigned_agent: Optional[str] = None
    assigned_agent_name: Optional[str] = None
    assigned_at: Optional[datetime] = None
    last_message_at: datetime = Field(default_factory=datetime.utcnow)
    last_reactivation_email_at: Optional[datetime] = None
    source: str = "whatsapp"
    referring_product_id: Optional[str] = None
    widget_session_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None
    conversation_history: List[dict] = Field(default_factory=list)

class LeadCreate(BaseModel):
    phone: str
    source: str = "whatsapp"

class LeadUpdate(BaseModel):
    name: Optional[str] = None
    appointment_datetime: Optional[datetime] = None
    flow_stage: Optional[FlowStage] = None
    intent: Optional[LeadIntent] = None
    zone: Optional[str] = None
    budget_text: Optional[str] = None
    property_type: Optional[PropertyType] = None
    bedrooms: Optional[int] = None
    must_have: Optional[List[str]] = None
    urgency: Optional[UrgencyLevel] = None
    financing: Optional[FinancingType] = None
    score: Optional[int] = None
    status: Optional[LeadStatus] = None
    notes: Optional[str] = None


# ============================================
# Agent Models (with tenant_id)
# ============================================

class Agent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tenant_id: str = ""
    name: str
    email: str
    phone: str
    password_hash: Optional[str] = None
    role: str = "asesor"  # superadmin, admin, asesor
    specialties: List[str] = Field(default_factory=list)
    zones: List[str] = Field(default_factory=list)
    max_concurrent_leads: int = 15
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AgentCreate(BaseModel):
    name: str
    email: str
    phone: str
    password: str
    specialties: List[str] = Field(default_factory=list)
    zones: List[str] = Field(default_factory=list)

class AgentLogin(BaseModel):
    email: str
    password: str

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str
    name: str
    role: str
    tenant_id: str = ""
    agent_data: Optional[dict] = None


# ============================================
# Bot Config (with tenant_id)
# ============================================

class BotConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tenant_id: str = ""
    business_hours_start: int = 9
    business_hours_end: int = 20
    business_days: List[str] = Field(default_factory=lambda: ["lunes", "martes", "miercoles", "jueves", "viernes"])
    saturday_hours_start: int = 10
    saturday_hours_end: int = 14
    timezone: str = "America/Argentina/Buenos_Aires"
    auto_handoff_score: int = 7
    warm_lead_reactivation_days: int = 3
    appointment_reminder_hours: int = 24
    welcome_message: str = "Hola! Soy el asistente virtual de la inmobiliaria. Estoy aca para ayudarte a encontrar tu propiedad ideal"
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================
# Other Models
# ============================================

class ConversationWindow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    customer_phone: str
    last_message_timestamp: datetime
    window_expires_at: datetime
    is_within_window: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

class EmailLog(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tenant_id: str = ""
    email_type: EmailType
    recipient_emails: List[str]
    lead_phone: Optional[str] = None
    subject: str
    success: bool
    error_message: Optional[str] = None
    sent_at: datetime = Field(default_factory=datetime.utcnow)

class WhatsAppTemplate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tenant_id: str = ""
    name: str
    category: str
    language: str = "es"
    status: str = "pending"
    content: str
    variables: List[str] = Field(default_factory=list)
    use_case: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
