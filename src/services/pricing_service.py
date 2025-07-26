from typing import Dict, List, Any
from datetime import datetime, timedelta
from src.agent.state import ProjectDetails, PricingInfo
from config.settings import settings


class PricingService:
    """Servicio para cálculos de precios y cotizaciones"""
    
    def __init__(self):
        self.base_delivery_cost = settings.base_delivery_cost
        self.cost_per_km = settings.cost_per_km
        self.weekend_surcharge = settings.weekend_surcharge
    
    def calculate_quote(
        self, 
        selected_equipment: List[Dict[str, Any]], 
        project_details: ProjectDetails
    ) -> PricingInfo:
        """Calcular cotización completa"""
        
        # Calcular subtotal de equipos
        equipment_subtotal = sum(item.get("subtotal", 0) for item in selected_equipment)
        
        # Calcular costo de entrega
        delivery_cost = self._calculate_delivery_cost(project_details.location)
        
        # Calcular costo de instalación
        setup_cost = self._calculate_setup_cost(selected_equipment)
        
        # Calcular seguro
        insurance_cost = self._calculate_insurance_cost(equipment_subtotal)
        
        # Calcular impuestos
        tax_amount = self._calculate_taxes(equipment_subtotal + delivery_cost + setup_cost)
        
        # Aplicar recargos por fechas especiales
        total_before_surcharge = equipment_subtotal + delivery_cost + setup_cost + insurance_cost + tax_amount
        surcharge_multiplier = self._get_date_surcharge_multiplier(project_details.start_date)
        
        total_amount = total_before_surcharge * surcharge_multiplier
        
        # Fecha de validez (7 días desde hoy)
        valid_until = datetime.now() + timedelta(days=7)
        
        return PricingInfo(
            equipment_subtotal=round(equipment_subtotal, 2),
            delivery_cost=round(delivery_cost, 2),
            setup_cost=round(setup_cost, 2),
            insurance_cost=round(insurance_cost, 2),
            tax_amount=round(tax_amount, 2),
            total_amount=round(total_amount, 2),
            currency=settings.default_currency,
            valid_until=valid_until
        )
    
    def _calculate_delivery_cost(self, location: str) -> float:
        """Calcular costo de entrega basado en ubicación"""
        
        if not location:
            return self.base_delivery_cost
        
        # Zonas de entrega simplificadas
        delivery_zones = {
            "zona_1": 0,  # Sin costo adicional
            "zona_2": 25,  # Costo adicional moderado
            "zona_3": 50,  # Costo adicional alto
        }
        
        # Mapeo simplificado de ubicaciones a zonas
        location_lower = location.lower()
        
        if any(city in location_lower for city in ["centro", "downtown", "bogotá centro"]):
            zone_cost = delivery_zones["zona_1"]
        elif any(city in location_lower for city in ["norte", "sur", "chapinero", "zona rosa"]):
            zone_cost = delivery_zones["zona_2"]
        else:
            zone_cost = delivery_zones["zona_3"]
        
        return self.base_delivery_cost + zone_cost
    
    def _calculate_setup_cost(self, selected_equipment: List[Dict[str, Any]]) -> float:
        """Calcular costo de instalación"""
        
        setup_cost = 0
        
        for equipment in selected_equipment:
            equipment_type = equipment.get("equipment_type", "")
            
            # Costos de instalación por tipo de equipo
            setup_rates = {
                "andamio": 100,  # Por unidad
                "plataforma_elevadora": 150,
                "escalera": 50,
                "grua": 300,
                "montacargas": 200
            }
            
            unit_setup_cost = setup_rates.get(equipment_type, 75)  # Default
            quantity = equipment.get("quantity", 1)
            setup_cost += unit_setup_cost * quantity
        
        return setup_cost
    
    def _calculate_insurance_cost(self, equipment_subtotal: float) -> float:
        """Calcular costo de seguro (porcentaje del subtotal)"""
        insurance_rate = 0.05  # 5% del subtotal de equipos
        return equipment_subtotal * insurance_rate
    
    def _calculate_taxes(self, subtotal: float) -> float:
        """Calcular impuestos"""
        tax_rate = 0.19  # IVA 19% en Colombia
        return subtotal * tax_rate
    
    def _get_date_surcharge_multiplier(self, start_date: datetime) -> float:
        """Obtener multiplicador de recargo por fecha"""
        
        if not start_date:
            return 1.0
        
        # Recargo por fin de semana
        if start_date.weekday() >= 5:  # Sábado o domingo
            return self.weekend_surcharge
        
        # Aquí se podrían agregar recargos por días festivos
        # holiday_dates = [...]
        # if start_date.date() in holiday_dates:
        #     return 1.5
        
        return 1.0
    
    def calculate_discount(self, total_amount: float, discount_type: str, discount_value: float) -> float:
        """Calcular descuento"""
        
        if discount_type == "percentage":
            discount = total_amount * (discount_value / 100)
        elif discount_type == "fixed":
            discount = discount_value
        else:
            discount = 0
        
        return min(discount, total_amount * 0.5)  # Máximo 50% de descuento
    
    def get_payment_terms(self) -> Dict[str, Any]:
        """Obtener términos de pago"""
        
        return {
            "payment_methods": ["efectivo", "transferencia", "tarjeta_credito"],
            "advance_payment": 0.3,  # 30% de anticipo
            "payment_terms_days": 30,
            "late_payment_fee": 0.02,  # 2% mensual por mora
            "damage_deposit": 0.2  # 20% del valor como depósito por daños
        }