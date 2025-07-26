from typing import TypedDict, List, Dict, Optional, Literal
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class ClientInfo:
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    contact_preference: Optional[str] = None


@dataclass
class ProjectDetails:
    project_type: Optional[str] = None  # "construccion", "mantenimiento", "limpieza", etc.
    location: Optional[str] = None
    address: Optional[str] = None
    duration_days: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    description: Optional[str] = None


@dataclass
class EquipmentNeed:
    equipment_type: Optional[str] = None  # "andamio", "plataforma", "escalera"
    height_needed: Optional[float] = None  # metros
    capacity_needed: Optional[float] = None  # kg
    quantity: Optional[int] = None
    specific_requirements: List[str] = field(default_factory=list)


@dataclass
class SiteConditions:
    surface_type: Optional[str] = None  # "concreto", "tierra", "asfalto"
    access_width: Optional[float] = None  # metros
    access_restrictions: List[str] = field(default_factory=list)
    power_available: Optional[bool] = None
    obstacles: List[str] = field(default_factory=list)


@dataclass
class SelectedEquipment:
    equipment_id: str
    equipment_name: str
    daily_rate: float
    quantity: int
    total_days: int
    subtotal: float
    specifications: Dict


@dataclass
class PricingInfo:
    equipment_subtotal: float = 0.0
    delivery_cost: float = 0.0
    setup_cost: float = 0.0
    insurance_cost: float = 0.0
    tax_amount: float = 0.0
    total_amount: float = 0.0
    currency: str = "USD"
    valid_until: Optional[datetime] = None


class ConversationMessage(TypedDict):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime
    message_type: Optional[str]  # "greeting", "question", "quote_request", etc.


class RentalAgentState(TypedDict):
    # Identificadores de sesión
    user_id: str
    chat_id: str
    session_id: str
    
    # Historial de conversación
    conversation_history: List[ConversationMessage]
    last_message: str
    
    # Información del cliente
    client_info: ClientInfo
    
    # Detalles del proyecto
    project_details: ProjectDetails
    
    # Necesidades de equipamiento
    equipment_needs: List[EquipmentNeed]
    
    # Condiciones del sitio
    site_conditions: SiteConditions
    
    # Proceso de cotización
    selected_equipment: List[SelectedEquipment]
    pricing_info: PricingInfo
    
    # Estado del flujo
    conversation_stage: Literal[
        "greeting",
        "gathering_basic_info", 
        "gathering_technical_info",
        "equipment_recommendation",
        "quote_generation",
        "quote_review",
        "scheduling",
        "completed",
        "escalated"
    ]
    
    # Contexto de la conversación
    current_topic: Optional[str]
    pending_questions: List[str]
    missing_information: List[str]
    
    # Control de flujo
    next_action: Optional[str]
    needs_human_intervention: bool
    escalation_reason: Optional[str]
    
    # Metadatos
    created_at: datetime
    updated_at: datetime
    language: str