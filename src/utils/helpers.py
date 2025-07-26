import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from sqlalchemy.exc import IntegrityError

from config.settings import settings
from src.database.session import get_db_session
from src.database.models import Equipment, Customer
from src.utils.constants import EquipmentType


def setup_logging():
    """Configurar sistema de logging"""
    
    # Crear directorio de logs si no existe
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configurar formato
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configurar handler para archivo
    file_handler = logging.FileHandler(
        log_dir / f"rental_bot_{datetime.now().strftime('%Y%m%d')}.log"
    )
    file_handler.setFormatter(log_format)
    file_handler.setLevel(logging.INFO)
    
    # Configurar handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    console_handler.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Configurar logger root
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Silenciar algunos loggers ruidosos
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)


async def load_initial_data():
    """Cargar datos iniciales en la base de datos"""
    
    try:
        # Cargar catálogo de equipos
        await load_equipment_catalog()
        
        # Cargar datos de configuración
        await load_business_configuration()
        
        logging.info("Initial data loaded successfully")
        
    except Exception as e:
        logging.error(f"Error loading initial data: {e}")
        raise


async def load_equipment_catalog():
    """Cargar catálogo de equipos desde archivo JSON"""
    
    catalog_file = Path("data/equipment_catalog.json")
    
    if not catalog_file.exists():
        logging.warning("Equipment catalog file not found, creating sample data...")
        await create_sample_equipment_data()
        return
    
    try:
        with open(catalog_file, 'r', encoding='utf-8') as f:
            catalog_data = json.load(f)
        
        with get_db_session() as db:
            for item in catalog_data.get("equipment", []):
                # Verificar si el equipo ya existe
                existing = db.query(Equipment).filter(
                    Equipment.name == item["name"]
                ).first()
                
                if not existing:
                    equipment = Equipment(
                        name=item["name"],
                        equipment_type=item["equipment_type"],
                        brand=item.get("brand"),
                        model=item.get("model"),
                        max_height=item["max_height"],
                        max_capacity=item["max_capacity"],
                        platform_size=item.get("platform_size"),
                        weight=item.get("weight"),
                        daily_rate=item["daily_rate"],
                        weekly_rate=item.get("weekly_rate"),
                        monthly_rate=item.get("monthly_rate"),
                        damage_deposit=item.get("damage_deposit", item["daily_rate"] * 5),
                        quantity_total=item.get("quantity_total", 1),
                        quantity_available=item.get("quantity_available", 1),
                        description=item.get("description", ""),
                        specifications=item.get("specifications", {}),
                        image_urls=item.get("image_urls", [])
                    )
                    db.add(equipment)
            
            db.commit()
            logging.info("Equipment catalog loaded successfully")
            
    except Exception as e:
        logging.error(f"Error loading equipment catalog: {e}")
        raise


async def create_sample_equipment_data():
    """Crear datos de ejemplo para equipos"""
    
    sample_equipment = [
        {
            "name": "Andamio Multidireccional 10m",
            "equipment_type": "andamio",
            "brand": "PERI",
            "model": "PERI UP",
            "max_height": 10.0,
            "max_capacity": 300.0,
            "platform_size": "3x2m",
            "weight": 850.0,
            "daily_rate": 45.0,
            "weekly_rate": 270.0,
            "monthly_rate": 1000.0,
            "damage_deposit": 225.0,
            "quantity_total": 5,
            "quantity_available": 5,
            "description": "Andamio multidireccional ideal para construcción y mantenimiento",
            "specifications": {
                "material": "Acero galvanizado",
                "certificacion": "ISO 9001",
                "peso_maximo_por_m2": "300kg"
            },
            "image_urls": []
        },
        {
            "name": "Plataforma Elevadora Tijera 8m",
            "equipment_type": "plataforma_elevadora",
            "brand": "JLG",
            "model": "2630ES",
            "max_height": 8.0,
            "max_capacity": 227.0,
            "platform_size": "2.4x1.2m",
            "weight": 1588.0,
            "daily_rate": 85.0,
            "weekly_rate": 510.0,
            "monthly_rate": 1900.0,
            "damage_deposit": 425.0,
            "quantity_total": 3,
            "quantity_available": 3,
            "description": "Plataforma elevadora eléctrica para interiores",
            "specifications": {
                "tipo_energia": "Eléctrica",
                "tiempo_elevacion": "60 segundos",
                "radio_giro": "Cero"
            },
            "image_urls": []
        },
        {
            "name": "Escalera Telescópica 6m",
            "equipment_type": "escalera",
            "brand": "WERNER",
            "model": "MT-22",
            "max_height": 6.0,
            "max_capacity": 136.0,
            "platform_size": "N/A",
            "weight": 28.0,
            "daily_rate": 15.0,
            "weekly_rate": 90.0,
            "monthly_rate": 350.0,
            "damage_deposit": 75.0,
            "quantity_total": 10,
            "quantity_available": 10,
            "description": "Escalera telescópica de fibra de vidrio",
            "specifications": {
                "material": "Fibra de vidrio",
                "peldanos": "22",
                "certificacion": "ANSI Type IA"
            },
            "image_urls": []
        },
        {
            "name": "Andamio Torre Móvil 8m",
            "equipment_type": "andamio",
            "brand": "LAYHER",
            "model": "Allround",
            "max_height": 8.0,
            "max_capacity": 200.0,
            "platform_size": "2x1.4m",
            "weight": 450.0,
            "daily_rate": 55.0,
            "weekly_rate": 330.0,
            "monthly_rate": 1200.0,
            "damage_deposit": 275.0,
            "quantity_total": 4,
            "quantity_available": 4,
            "description": "Torre móvil con ruedas para trabajos ligeros",
            "specifications": {
                "ruedas": "125mm con freno",
                "estabilizadores": "4 unidades",
                "montaje": "Sin herramientas"
            },
            "image_urls": []
        },
        {
            "name": "Plataforma Articulada 12m",
            "equipment_type": "plataforma_elevadora",
            "brand": "GENIE",
            "model": "Z-34/22N",
            "max_height": 12.0,
            "max_capacity": 227.0,
            "platform_size": "1.8x0.9m",
            "weight": 6985.0,
            "daily_rate": 125.0,
            "weekly_rate": 750.0,
            "monthly_rate": 2800.0,
            "damage_deposit": 625.0,
            "quantity_total": 2,
            "quantity_available": 2,
            "description": "Plataforma articulada para espacios reducidos",
            "specifications": {
                "alcance_horizontal": "6.1m",
                "tipo_traccion": "4x4",
                "combustible": "Diesel"
            },
            "image_urls": []
        }
    ]
    
    try:
        with get_db_session() as db:
            for item in sample_equipment:
                equipment = Equipment(**item)
                db.add(equipment)
            
            db.commit()
            logging.info("Sample equipment data created successfully")
            
    except Exception as e:
        logging.error(f"Error creating sample equipment data: {e}")
        raise


async def load_business_configuration():
    """Cargar configuración de negocio"""
    
    config_file = Path("data/business_rules.json")
    
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Aquí se podría cargar configuración adicional
            # Por ahora solo registramos que se cargó
            logging.info("Business configuration loaded")
            
        except Exception as e:
            logging.error(f"Error loading business configuration: {e}")
    else:
        logging.warning("Business rules file not found, using defaults")


def format_currency(amount: float, currency: str = "USD") -> str:
    """Formatear cantidad como moneda"""
    
    if currency == "USD":
        return f"${amount:,.2f}"
    elif currency == "COP":
        return f"${amount:,.0f} COP"
    else:
        return f"{amount:,.2f} {currency}"


def format_phone_number(phone: str) -> str:
    """Formatear número de teléfono"""
    
    # Remover caracteres no numéricos
    clean_phone = ''.join(filter(str.isdigit, phone))
    
    # Formatear según longitud
    if len(clean_phone) == 10:
        # Formato colombiano: (XXX) XXX-XXXX
        return f"({clean_phone[:3]}) {clean_phone[3:6]}-{clean_phone[6:]}"
    elif len(clean_phone) == 7:
        # Formato local: XXX-XXXX
        return f"{clean_phone[:3]}-{clean_phone[3:]}"
    else:
        # Devolver tal como está si no coincide con formatos conocidos
        return phone


def calculate_business_days(start_date: datetime, end_date: datetime) -> int:
    """Calcular días hábiles entre dos fechas"""
    
    current_date = start_date.date()
    end_date = end_date.date()
    business_days = 0
    
    while current_date <= end_date:
        # Monday = 0, Sunday = 6
        if current_date.weekday() < 5:  # Monday to Friday
            business_days += 1
        current_date += datetime.timedelta(days=1)
    
    return business_days


def generate_quote_number() -> str:
    """Generar número de cotización único"""
    
    from datetime import datetime
    import random
    
    # Formato: COT-YYYYMMDD-XXXX
    date_part = datetime.now().strftime("%Y%m%d")
    random_part = f"{random.randint(1000, 9999)}"
    
    return f"COT-{date_part}-{random_part}"


def clean_text_for_telegram(text: str) -> str:
    """Limpiar texto para evitar problemas con markdown de Telegram"""
    
    # Escapar caracteres especiales de markdown
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text


async def health_check() -> Dict[str, Any]:
    """Verificación de salud del sistema"""
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {}
    }
    
    try:
        # Verificar base de datos
        with get_db_session() as db:
            equipment_count = db.query(Equipment).count()
            health_status["services"]["database"] = {
                "status": "healthy",
                "equipment_count": equipment_count
            }
    except Exception as e:
        health_status["services"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    try:
        # Verificar Redis (state manager)
        from src.database.session import state_manager
        test_key = "health_check_test"
        state_manager.redis.set(test_key, "test", ex=60)
        state_manager.redis.delete(test_key)
        
        health_status["services"]["redis"] = {
            "status": "healthy"
        }
    except Exception as e:
        health_status["services"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    return health_status