from enum import Enum
from typing import Dict, List


class EquipmentType(Enum):
    SCAFFOLD = "andamio"
    AERIAL_PLATFORM = "plataforma_elevadora"
    LADDER = "escalera"
    CRANE = "grua"
    HOIST = "montacargas"


class ProjectType(Enum):
    CONSTRUCTION = "construccion"
    MAINTENANCE = "mantenimiento"
    CLEANING = "limpieza"
    PAINTING = "pintura"
    RENOVATION = "renovacion"
    INDUSTRIAL = "industrial"


class SurfaceType(Enum):
    CONCRETE = "concreto"
    ASPHALT = "asfalto"
    DIRT = "tierra"
    GRASS = "cesped"
    GRAVEL = "grava"
    TILE = "baldosa"


class ConversationStage(Enum):
    GREETING = "greeting"
    GATHERING_BASIC_INFO = "gathering_basic_info"
    GATHERING_TECHNICAL_INFO = "gathering_technical_info"
    EQUIPMENT_RECOMMENDATION = "equipment_recommendation"
    QUOTE_GENERATION = "quote_generation"
    QUOTE_REVIEW = "quote_review"
    SCHEDULING = "scheduling"
    COMPLETED = "completed"
    ESCALATED = "escalated"


# Preguntas por etapa de conversación
STAGE_QUESTIONS = {
    ConversationStage.GATHERING_BASIC_INFO: [
        "¿Qué tipo de trabajo vas a realizar?",
        "¿En qué ubicación será el proyecto?",
        "¿Por cuántos días aproximadamente necesitas el equipo?",
        "¿Cuándo planeas comenzar el trabajo?"
    ],
    ConversationStage.GATHERING_TECHNICAL_INFO: [
        "¿A qué altura necesitas llegar?",
        "¿Cuánto peso necesitas soportar?",
        "¿Qué tipo de superficie tienes en el lugar?",
        "¿Hay restricciones de acceso al sitio?",
        "¿Tienes energía eléctrica disponible?"
    ]
}

# Información técnica por tipo de equipo
EQUIPMENT_SPECS = {
    EquipmentType.SCAFFOLD: {
        "height_range": (2, 50),  # metros
        "capacity_range": (150, 500),  # kg por m²
        "setup_time": "2-4 horas",
        "requires_certification": True
    },
    EquipmentType.AERIAL_PLATFORM: {
        "height_range": (4, 30),
        "capacity_range": (200, 1000),
        "setup_time": "30-60 minutos",
        "requires_certification": True
    },
    EquipmentType.LADDER: {
        "height_range": (2, 12),
        "capacity_range": (120, 150),
        "setup_time": "5-15 minutos",
        "requires_certification": False
    }
}

# Reglas de negocio
BUSINESS_RULES = {
    "minimum_rental_days": 1,
    "maximum_rental_days": 365,
    "delivery_radius_km": 50,
    "weekend_surcharge": 1.2,
    "holiday_surcharge": 1.5,
    "damage_deposit_percentage": 0.2,
    "cancellation_hours": 24
}

# Mensajes del sistema
SYSTEM_MESSAGES = {
    "greeting": """¡Hola! Soy el asistente de {company_name}. 
Estoy aquí para ayudarte a encontrar el equipo de altura perfecto para tu proyecto.

¿En qué puedo ayudarte hoy?
- Cotizar equipos de altura
- Información técnica sobre nuestros equipos
- Consultar disponibilidad
- Programar una visita técnica""",
    
    "information_gathering": "Para darte la mejor recomendación, necesito conocer algunos detalles sobre tu proyecto.",
    
    "quote_ready": "Perfecto! He preparado una cotización basada en tus necesidades:",
    
    "escalation": "Te voy a conectar con uno de nuestros especialistas para que te ayude con esta consulta específica.",
    
    "goodbye": "Gracias por contactar a {company_name}. ¡Esperamos trabajar contigo pronto!"
}

# Patrones de regex para extracción de información
EXTRACTION_PATTERNS = {
    "height": r"(\d+(?:\.\d+)?)\s*(?:metros?|m|mts?)",
    "weight": r"(\d+(?:\.\d+)?)\s*(?:kg|kilos?|kilogramos?|toneladas?|t)",
    "days": r"(\d+)\s*(?:días?|day|days)",
    "phone": r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
}

# Respuestas de error
ERROR_MESSAGES = {
    "invalid_height": "La altura debe estar entre 2 y 50 metros.",
    "invalid_capacity": "La capacidad debe estar entre 100 y 1000 kg.",
    "invalid_duration": "La duración debe estar entre 1 y 365 días.",
    "missing_information": "Necesito más información para continuar.",
    "technical_error": "Ha ocurrido un error técnico. Te conectaré con un especialista.",
    "out_of_service_area": "Lamentablemente no prestamos servicio en esa ubicación."
}