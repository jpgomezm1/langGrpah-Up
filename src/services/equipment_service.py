from typing import List, Dict, Any, Optional
from dataclasses import asdict
from src.agent.state import EquipmentNeed, SiteConditions, ProjectDetails
from src.database.session import get_db_session
from src.database.models import Equipment
from src.utils.constants import EquipmentType, EQUIPMENT_SPECS
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_


class EquipmentService:
    """Servicio para manejo de equipos y recomendaciones"""
    
    def __init__(self):
        pass
    
    def get_recommendations(
        self, 
        equipment_needs: List[EquipmentNeed], 
        site_conditions: SiteConditions, 
        project_details: ProjectDetails
    ) -> List[Dict[str, Any]]:
        """Obtener recomendaciones de equipos basado en necesidades"""
        
        if not equipment_needs:
            return []
        
        primary_need = equipment_needs[0]
        
        with get_db_session() as db:
            # Construir query base
            query = db.query(Equipment).filter(
                Equipment.is_available == True,
                Equipment.quantity_available > 0
            )
            
            # Filtrar por altura si está especificada
            if primary_need.height_needed:
                query = query.filter(
                    Equipment.max_height >= primary_need.height_needed
                )
            
            # Filtrar por capacidad si está especificada
            if primary_need.capacity_needed:
                query = query.filter(
                    Equipment.max_capacity >= primary_need.capacity_needed
                )
            
            # Filtrar por tipo de equipo si está especificado
            if primary_need.equipment_type:
                query = query.filter(
                    Equipment.equipment_type == primary_need.equipment_type
                )
            
            # Obtener equipos que cumplen los criterios
            equipment_list = query.all()
            
            # Convertir a formato de respuesta
            recommendations = []
            for equipment in equipment_list:
                recommendation = {
                    "id": equipment.id,
                    "name": equipment.name,
                    "equipment_type": equipment.equipment_type,
                    "max_height": equipment.max_height,
                    "max_capacity": equipment.max_capacity,
                    "daily_rate": equipment.daily_rate,
                    "weekly_rate": equipment.weekly_rate,
                    "monthly_rate": equipment.monthly_rate,
                    "platform_size": equipment.platform_size,
                    "description": equipment.description,
                    "quantity": primary_need.quantity or 1,
                    "subtotal": self._calculate_equipment_subtotal(
                        equipment, 
                        project_details.duration_days or 1,
                        primary_need.quantity or 1
                    ),
                    "suitability_score": self._calculate_suitability_score(
                        equipment, primary_need, site_conditions
                    )
                }
                recommendations.append(recommendation)
            
            # Ordenar por puntaje de adecuación
            recommendations.sort(
                key=lambda x: x["suitability_score"], 
                reverse=True
            )
            
            # Retornar máximo 3 recomendaciones
            return recommendations[:3]
    
    def _calculate_equipment_subtotal(
        self, 
        equipment: Equipment, 
        duration_days: int, 
        quantity: int
    ) -> float:
        """Calcular subtotal para un equipo"""
        
        # Determinar tarifa más económica según duración
        if duration_days >= 30 and equipment.monthly_rate:
            months = duration_days / 30
            rate = equipment.monthly_rate * months
        elif duration_days >= 7 and equipment.weekly_rate:
            weeks = duration_days / 7
            rate = equipment.weekly_rate * weeks
        else:
            rate = equipment.daily_rate * duration_days
        
        return rate * quantity
    
    def _calculate_suitability_score(
        self, 
        equipment: Equipment, 
        need: EquipmentNeed, 
        conditions: SiteConditions
    ) -> float:
        """Calcular puntaje de adecuación del equipo"""
        
        score = 0.0
        
        # Puntaje por altura (mayor si está cerca del requerimiento)
        if need.height_needed and equipment.max_height:
            if equipment.max_height >= need.height_needed:
                # Bonificación si está cerca del requerimiento (no excesivamente grande)
                height_ratio = need.height_needed / equipment.max_height
                score += height_ratio * 30
            else:
                # Penalización si no alcanza la altura
                score -= 20
        
        # Puntaje por capacidad
        if need.capacity_needed and equipment.max_capacity:
            if equipment.max_capacity >= need.capacity_needed:
                capacity_ratio = need.capacity_needed / equipment.max_capacity
                score += capacity_ratio * 25
            else:
                score -= 15
        
        # Puntaje por tipo de equipo exacto
        if need.equipment_type and equipment.equipment_type == need.equipment_type:
            score += 20
        
        # Puntaje por condiciones del sitio
        if conditions.surface_type:
            if self._is_suitable_for_surface(equipment, conditions.surface_type):
                score += 15
        
        # Puntaje por disponibilidad
        if equipment.quantity_available >= (need.quantity or 1):
            score += 10
        
        return max(0, score)
    
    def _is_suitable_for_surface(self, equipment: Equipment, surface_type: str) -> bool:
        """Verificar si el equipo es adecuado para el tipo de superficie"""
        
        # Reglas simplificadas - en producción esto sería más complejo
        surface_compatibility = {
            "andamio": ["concreto", "asfalto", "baldosa"],
            "plataforma_elevadora": ["concreto", "asfalto"],
            "escalera": ["concreto", "asfalto", "baldosa", "cesped"]
        }
        
        compatible_surfaces = surface_compatibility.get(equipment.equipment_type, [])
        return surface_type in compatible_surfaces
    
    def get_equipment_by_id(self, equipment_id: str) -> Optional[Dict[str, Any]]:
        """Obtener equipo por ID"""
        
        with get_db_session() as db:
            equipment = db.query(Equipment).filter(
                Equipment.id == equipment_id
            ).first()
            
            if equipment:
                return {
                    "id": equipment.id,
                    "name": equipment.name,
                    "equipment_type": equipment.equipment_type,
                    "max_height": equipment.max_height,
                    "max_capacity": equipment.max_capacity,
                    "daily_rate": equipment.daily_rate,
                    "weekly_rate": equipment.weekly_rate,
                    "monthly_rate": equipment.monthly_rate,
                    "description": equipment.description,
                    "specifications": equipment.specifications,
                    "quantity_available": equipment.quantity_available
                }
            
            return None
    
    def check_availability(
        self, 
        equipment_id: str, 
        start_date: str, 
        end_date: str, 
        quantity: int = 1
    ) -> bool:
        """Verificar disponibilidad de equipo en fechas específicas"""
        
        with get_db_session() as db:
            equipment = db.query(Equipment).filter(
                Equipment.id == equipment_id
            ).first()
            
            if not equipment:
                return False
            
            # Verificar disponibilidad básica
            if equipment.quantity_available < quantity:
                return False
            
            # Aquí se podría agregar lógica más compleja para verificar
            # reservas existentes en las fechas solicitadas
            
            return True
    
    def get_equipment_catalog(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Obtener catálogo de equipos"""
        
        with get_db_session() as db:
            query = db.query(Equipment).filter(Equipment.is_available == True)
            
            if category:
                query = query.filter(Equipment.equipment_type == category)
            
            equipment_list = query.all()
            
            catalog = []
            for equipment in equipment_list:
                catalog.append({
                    "id": equipment.id,
                    "name": equipment.name,
                    "equipment_type": equipment.equipment_type,
                    "max_height": equipment.max_height,
                    "max_capacity": equipment.max_capacity,
                    "daily_rate": equipment.daily_rate,
                    "description": equipment.description,
                    "image_urls": equipment.image_urls
                })
            
            return catalog