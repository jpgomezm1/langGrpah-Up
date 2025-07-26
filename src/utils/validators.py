import re
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from src.utils.constants import BUSINESS_RULES, EQUIPMENT_SPECS, EquipmentType


class ValidationError(Exception):
    """Excepción personalizada para errores de validación"""
    pass


class ProjectValidator:
    """Validador para datos de proyecto"""
    
    @staticmethod
    def validate_height(height: float) -> bool:
        """Validar altura solicitada"""
        if not isinstance(height, (int, float)):
            raise ValidationError("La altura debe ser un número")
        
        if height < 2:
            raise ValidationError("La altura mínima es 2 metros")
        
        if height > 50:
            raise ValidationError("La altura máxima es 50 metros")
        
        return True
    
    @staticmethod
    def validate_capacity(capacity: float) -> bool:
        """Validar capacidad solicitada"""
        if not isinstance(capacity, (int, float)):
            raise ValidationError("La capacidad debe ser un número")
        
        if capacity < 100:
            raise ValidationError("La capacidad mínima es 100 kg")
        
        if capacity > 2000:
            raise ValidationError("La capacidad máxima es 2000 kg")
        
        return True
    
    @staticmethod
    def validate_duration(duration_days: int) -> bool:
        """Validar duración del alquiler"""
        if not isinstance(duration_days, int):
            raise ValidationError("La duración debe ser un número entero de días")
        
        min_days = BUSINESS_RULES["minimum_rental_days"]
        max_days = BUSINESS_RULES["maximum_rental_days"]
        
        if duration_days < min_days:
            raise ValidationError(f"La duración mínima es {min_days} días")
        
        if duration_days > max_days:
            raise ValidationError(f"La duración máxima es {max_days} días")
        
        return True
    
    @staticmethod
    def validate_location(location: str) -> bool:
        """Validar ubicación del proyecto"""
        if not location or len(location.strip()) < 3:
            raise ValidationError("La ubicación debe tener al menos 3 caracteres")
        
        if len(location) > 200:
            raise ValidationError("La ubicación es muy larga (máximo 200 caracteres)")
        
        # Verificar que no contenga solo números o caracteres especiales
        if re.match(r'^[\d\s\-_.,]+$', location.strip()):
            raise ValidationError("La ubicación debe incluir nombres de lugares")
        
        return True
    
    @staticmethod
    def validate_start_date(start_date: datetime) -> bool:
        """Validar fecha de inicio"""
        if not isinstance(start_date, datetime):
            raise ValidationError("La fecha de inicio debe ser válida")
        
        # No puede ser en el pasado (con margen de 1 día)
        yesterday = datetime.now() - timedelta(days=1)
        if start_date < yesterday:
            raise ValidationError("La fecha de inicio no puede ser en el pasado")
        
        # No puede ser más de 1 año en el futuro
        max_future_date = datetime.now() + timedelta(days=365)
        if start_date > max_future_date:
            raise ValidationError("La fecha de inicio no puede ser más de 1 año en el futuro")
        
        return True


class ContactValidator:
    """Validador para información de contacto"""
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validar número de teléfono"""
        if not phone:
            return True  # Opcional
        
        # Remover espacios y caracteres especiales para validación
        clean_phone = re.sub(r'[\s\-\(\)\+]', '', phone)
        
        # Verificar que contenga solo dígitos
        if not clean_phone.isdigit():
            raise ValidationError("El teléfono debe contener solo números")
        
        # Verificar longitud (7-15 dígitos)
        if len(clean_phone) < 7 or len(clean_phone) > 15:
            raise ValidationError("El teléfono debe tener entre 7 y 15 dígitos")
        
        return True
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validar dirección de email"""
        if not email:
            return True  # Opcional
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(email_pattern, email):
            raise ValidationError("El formato del email no es válido")
        
        if len(email) > 100:
            raise ValidationError("El email es muy largo (máximo 100 caracteres)")
        
        return True
    
    @staticmethod
    def validate_name(name: str) -> bool:
        """Validar nombre"""
        if not name:
            return True  # Opcional
        
        if len(name.strip()) < 2:
            raise ValidationError("El nombre debe tener al menos 2 caracteres")
        
        if len(name) > 100:
            raise ValidationError("El nombre es muy largo (máximo 100 caracteres)")
        
        # Verificar que contenga principalmente letras
        if not re.match(r'^[a-zA-ZáéíóúñÁÉÍÓÚÑ\s\-\.]+$', name):
            raise ValidationError("El nombre contiene caracteres no válidos")
        
        return True


class EquipmentValidator:
    """Validador para equipos"""
    
    @staticmethod
    def validate_equipment_compatibility(
        equipment_type: str, 
        height: float, 
        capacity: float,
        surface_type: str = None
    ) -> bool:
        """Validar compatibilidad de equipo con requerimientos"""
        
        # Verificar que el tipo de equipo existe
        valid_types = [eq_type.value for eq_type in EquipmentType]
        if equipment_type not in valid_types:
            raise ValidationError(f"Tipo de equipo no válido: {equipment_type}")
        
        # Obtener especificaciones del tipo de equipo
        for eq_type in EquipmentType:
            if eq_type.value == equipment_type:
                specs = EQUIPMENT_SPECS.get(eq_type)
                if specs:
                    # Validar altura
                    min_height, max_height = specs["height_range"]
                    if height < min_height or height > max_height:
                        raise ValidationError(
                            f"El {equipment_type} no puede alcanzar {height}m "
                            f"(rango: {min_height}-{max_height}m)"
                        )
                    
                    # Validar capacidad
                    min_capacity, max_capacity = specs["capacity_range"]
                    if capacity < min_capacity or capacity > max_capacity:
                        raise ValidationError(
                            f"El {equipment_type} no puede soportar {capacity}kg "
                            f"(rango: {min_capacity}-{max_capacity}kg)"
                        )
                break
        
        return True
    
    @staticmethod
    def validate_quantity(quantity: int, available_quantity: int) -> bool:
        """Validar cantidad solicitada vs disponible"""
        if not isinstance(quantity, int) or quantity < 1:
            raise ValidationError("La cantidad debe ser un número entero mayor a 0")
        
        if quantity > available_quantity:
            raise ValidationError(
                f"Solo hay {available_quantity} unidades disponibles, "
                f"solicitaste {quantity}"
            )
        
        if quantity > 10:
            raise ValidationError("No puedes solicitar más de 10 unidades por pedido")
        
        return True


class BusinessRulesValidator:
    """Validador para reglas de negocio"""
    
    @staticmethod
    def validate_delivery_location(location: str) -> bool:
        """Validar que la ubicación esté dentro del área de servicio"""
        # Implementación simplificada
        # En producción esto consultaría una base de datos de zonas de cobertura
        
        restricted_keywords = [
            "internacional", "extranjero", "exterior", "fuera del país"
        ]
        
        location_lower = location.lower()
        for keyword in restricted_keywords:
            if keyword in location_lower:
                raise ValidationError("No prestamos servicio fuera del país")
        
        return True
    
    @staticmethod
    def validate_rental_dates(start_date: datetime, end_date: datetime) -> bool:
        """Validar fechas de alquiler"""
        if end_date <= start_date:
            raise ValidationError("La fecha de fin debe ser posterior a la fecha de inicio")
        
        # Calcular duración
        duration = (end_date - start_date).days
        
        # Aplicar validación de duración
        ProjectValidator.validate_duration(duration)
        
        return True
    
    @staticmethod
    def validate_cancellation_policy(
        start_date: datetime, 
        cancellation_date: datetime = None
    ) -> bool:
        """Validar política de cancelación"""
        if not cancellation_date:
            cancellation_date = datetime.now()
        
        hours_until_start = (start_date - cancellation_date).total_seconds() / 3600
        min_hours = BUSINESS_RULES["cancellation_hours"]
        
        if hours_until_start < min_hours:
            raise ValidationError(
                f"Las cancelaciones deben hacerse con al menos {min_hours} horas de anticipación"
            )
        
        return True


def validate_complete_request(request_data: Dict[str, Any]) -> List[str]:
    """Validar una solicitud completa y retornar lista de errores"""
    
    errors = []
    
    try:
        # Validar datos del proyecto
        if "height" in request_data:
            ProjectValidator.validate_height(request_data["height"])
        
        if "capacity" in request_data:
            ProjectValidator.validate_capacity(request_data["capacity"])
        
        if "duration_days" in request_data:
            ProjectValidator.validate_duration(request_data["duration_days"])
        
        if "location" in request_data:
            ProjectValidator.validate_location(request_data["location"])
            BusinessRulesValidator.validate_delivery_location(request_data["location"])
        
        if "start_date" in request_data:
            ProjectValidator.validate_start_date(request_data["start_date"])
        
        # Validar datos de contacto
        if "phone" in request_data:
            ContactValidator.validate_phone(request_data["phone"])
        
        if "email" in request_data:
            ContactValidator.validate_email(request_data["email"])
        
        if "name" in request_data:
            ContactValidator.validate_name(request_data["name"])
        
        # Validar compatibilidad de equipo
        if all(key in request_data for key in ["equipment_type", "height", "capacity"]):
            EquipmentValidator.validate_equipment_compatibility(
                request_data["equipment_type"],
                request_data["height"],
                request_data["capacity"],
                request_data.get("surface_type")
            )
        
    except ValidationError as e:
        errors.append(str(e))
    except Exception as e:
        errors.append(f"Error de validación: {str(e)}")
    
    return errors