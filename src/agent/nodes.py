from typing import Dict, List, Any
from datetime import datetime, timedelta
import re
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

from src.agent.state import RentalAgentState, ConversationMessage, ClientInfo, ProjectDetails, EquipmentNeed, SiteConditions
from src.utils.constants import ConversationStage, SYSTEM_MESSAGES, STAGE_QUESTIONS, EXTRACTION_PATTERNS
from src.services.equipment_service import EquipmentService
from src.services.pricing_service import PricingService
from config.settings import settings


class AgentNodes:
    """Nodos del grafo LangGraph para el agente de alquiler"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0.3,
            api_key=settings.openai_api_key
        )
        self.equipment_service = EquipmentService()
        self.pricing_service = PricingService()
    
    def message_router(self, state: RentalAgentState) -> RentalAgentState:
        """Nodo para clasificar y rutear mensajes entrantes"""
        
        last_message = state["last_message"].lower()
        current_stage = state["conversation_stage"]
        
        # Palabras clave para clasificación
        greeting_keywords = ["hola", "buenos días", "buenas tardes", "buenas", "hey", "hi"]
        quote_keywords = ["cotización", "precio", "costo", "cuanto cuesta", "presupuesto"]
        technical_keywords = ["altura", "andamio", "plataforma", "escalera", "metros", "kg"]
        contact_keywords = ["contacto", "teléfono", "email", "dirección"]
        
        # Determinar el próximo nodo basado en el contenido del mensaje
        if any(keyword in last_message for keyword in greeting_keywords) and current_stage == "greeting":
            next_action = "conversation_manager"
            conversation_stage = "gathering_basic_info"
        elif any(keyword in last_message for keyword in quote_keywords):
            next_action = "information_gatherer"
            conversation_stage = "gathering_technical_info"
        elif any(keyword in last_message for keyword in technical_keywords):
            next_action = "equipment_advisor" 
            conversation_stage = "equipment_recommendation"
        elif any(keyword in last_message for keyword in contact_keywords):
            next_action = "conversation_manager"
        else:
            # Continuar con el flujo normal basado en la etapa actual
            stage_mapping = {
                "gathering_basic_info": "information_gatherer",
                "gathering_technical_info": "information_gatherer", 
                "equipment_recommendation": "equipment_advisor",
                "quote_generation": "quote_calculator",
                "quote_review": "conversation_manager"
            }
            next_action = stage_mapping.get(current_stage, "conversation_manager")
            conversation_stage = current_stage
        
        # Actualizar estado
        state["next_action"] = next_action
        state["conversation_stage"] = conversation_stage
        state["updated_at"] = datetime.now()
        
        return state
    
    def information_gatherer(self, state: RentalAgentState) -> RentalAgentState:
        """Nodo para recopilar información faltante"""
        
        current_stage = state["conversation_stage"]
        last_message = state["last_message"]
        
        # Extraer información del último mensaje
        self._extract_information_from_message(state, last_message)
        
        # Determinar qué información falta
        missing_info = self._identify_missing_information(state)
        
        if missing_info:
            # Generar pregunta contextual
            question = self._generate_contextual_question(state, missing_info[0])
            response_message = question
            next_action = "information_gatherer"
        else:
            # Toda la información recopilada, pasar al siguiente paso
            if current_stage == "gathering_basic_info":
                response_message = "Perfecto! Ahora necesito algunos detalles técnicos para recomendarte el mejor equipo."
                state["conversation_stage"] = "gathering_technical_info"
                next_action = "information_gatherer"
            else:
                response_message = "Excelente! Con esta información puedo recomendarte los equipos más adecuados."
                state["conversation_stage"] = "equipment_recommendation"
                next_action = "equipment_advisor"
        
        # Agregar mensaje a la conversación
        self._add_message_to_history(state, "assistant", response_message)
        
        state["next_action"] = next_action
        state["missing_information"] = missing_info
        state["updated_at"] = datetime.now()
        
        return state
    
    def equipment_advisor(self, state: RentalAgentState) -> RentalAgentState:
        """Nodo para recomendar equipos basado en las necesidades"""
        
        # Obtener recomendaciones de equipos
        equipment_needs = state["equipment_needs"]
        site_conditions = state["site_conditions"]
        project_details = state["project_details"]
        
        recommendations = self.equipment_service.get_recommendations(
            equipment_needs, site_conditions, project_details
        )
        
        if not recommendations:
            # No hay equipos disponibles
            response_message = """Lo siento, no tengo equipos disponibles que cumplan exactamente con tus requisitos. 
Te voy a conectar con uno de nuestros especialistas para revisar opciones alternativas."""
            
            state["needs_human_intervention"] = True
            state["escalation_reason"] = "No equipment available for requirements"
            state["next_action"] = "escalation_handler"
        else:
            # Generar respuesta con recomendaciones
            response_message = self._format_equipment_recommendations(recommendations)
            state["selected_equipment"] = recommendations
            state["conversation_stage"] = "quote_generation"
            state["next_action"] = "quote_calculator"
        
        self._add_message_to_history(state, "assistant", response_message)
        state["updated_at"] = datetime.now()
        
        return state
    
    def quote_calculator(self, state: RentalAgentState) -> RentalAgentState:
        """Nodo para calcular cotizaciones"""
        
        selected_equipment = state["selected_equipment"]
        project_details = state["project_details"]
        
        # Calcular pricing
        pricing_info = self.pricing_service.calculate_quote(
            selected_equipment, project_details
        )
        
        state["pricing_info"] = pricing_info
        
        # Generar respuesta con cotización
        response_message = self._format_quote_response(pricing_info, selected_equipment)
        
        self._add_message_to_history(state, "assistant", response_message)
        
        state["conversation_stage"] = "quote_review"
        state["next_action"] = "conversation_manager"
        state["updated_at"] = datetime.now()
        
        return state
    
    def conversation_manager(self, state: RentalAgentState) -> RentalAgentState:
        """Nodo para manejar la fluidez conversacional"""
        
        last_message = state["last_message"]
        current_stage = state["conversation_stage"]
        
        # Generar respuesta contextual usando LLM
        system_prompt = self._build_system_prompt(state)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=last_message)
        ]
        
        response = self.llm(messages)
        response_message = response.content
        
        # Determinar siguiente acción basada en la respuesta
        next_action = self._determine_next_action_from_response(state, response_message)
        
        self._add_message_to_history(state, "assistant", response_message)
        
        state["next_action"] = next_action
        state["updated_at"] = datetime.now()
        
        return state
    
    def escalation_handler(self, state: RentalAgentState) -> RentalAgentState:
        """Nodo para escalar a agentes humanos"""
        
        escalation_reason = state.get("escalation_reason", "Usuario solicita escalación")
        
        response_message = f"""Te voy a conectar con uno de nuestros especialistas que podrá ayudarte mejor con tu consulta.

📞 Puedes llamarnos al: {settings.support_phone}
📧 O escribirnos a: {settings.support_email}

Mientras tanto, ¿hay algo más en lo que pueda ayudarte?"""
        
        self._add_message_to_history(state, "assistant", response_message)
        
        state["conversation_stage"] = "escalated"
        state["needs_human_intervention"] = True
        state["next_action"] = "conversation_manager"
        state["updated_at"] = datetime.now()
        
        return state
    
    # Métodos auxiliares
    
    def _extract_information_from_message(self, state: RentalAgentState, message: str):
        """Extraer información estructurada del mensaje"""
        
        # Extraer altura
        height_match = re.search(EXTRACTION_PATTERNS["height"], message, re.IGNORECASE)
        if height_match:
            height = float(height_match.group(1))
            if not state["equipment_needs"]:
                state["equipment_needs"] = [EquipmentNeed()]
            state["equipment_needs"][0].height_needed = height
        
        # Extraer peso/capacidad
        weight_match = re.search(EXTRACTION_PATTERNS["weight"], message, re.IGNORECASE)
        if weight_match:
            weight = float(weight_match.group(1))
            if not state["equipment_needs"]:
                state["equipment_needs"] = [EquipmentNeed()]
            state["equipment_needs"][0].capacity_needed = weight
        
        # Extraer duración
        days_match = re.search(EXTRACTION_PATTERNS["days"], message, re.IGNORECASE)
        if days_match:
            days = int(days_match.group(1))
            state["project_details"].duration_days = days
        
        # Extraer teléfono
        phone_match = re.search(EXTRACTION_PATTERNS["phone"], message)
        if phone_match:
            state["client_info"].phone = phone_match.group(0)
        
        # Extraer email
        email_match = re.search(EXTRACTION_PATTERNS["email"], message)
        if email_match:
            state["client_info"].email = email_match.group(0)
    
    def _identify_missing_information(self, state: RentalAgentState) -> List[str]:
        """Identificar información faltante según la etapa"""
        
        missing = []
        stage = state["conversation_stage"]
        
        if stage == "gathering_basic_info":
            if not state["project_details"].project_type:
                missing.append("project_type")
            if not state["project_details"].location:
                missing.append("location")
            if not state["project_details"].duration_days:
                missing.append("duration")
                
        elif stage == "gathering_technical_info":
            if not state["equipment_needs"] or not state["equipment_needs"][0].height_needed:
                missing.append("height")
            if not state["equipment_needs"] or not state["equipment_needs"][0].equipment_type:
                missing.append("equipment_type")
            if not state["site_conditions"].surface_type:
                missing.append("surface_type")
        
        return missing
    
    def _generate_contextual_question(self, state: RentalAgentState, missing_info: str) -> str:
        """Generar pregunta contextual para información faltante"""
        
        questions = {
            "project_type": "¿Qué tipo de trabajo vas a realizar? (construcción, mantenimiento, limpieza, etc.)",
            "location": "¿En qué ciudad o zona será el proyecto?",
            "duration": "¿Por cuántos días aproximadamente necesitas el equipo?",
            "height": "¿A qué altura necesitas llegar?",
            "equipment_type": "¿Qué tipo de equipo prefieres? (andamio, plataforma elevadora, escalera)",
            "surface_type": "¿Qué tipo de superficie tienes en el lugar? (concreto, asfalto, tierra, etc.)"
        }
        
        return questions.get(missing_info, "¿Podrías darme más detalles sobre tu proyecto?")
    
    def _format_equipment_recommendations(self, recommendations: List[Dict]) -> str:
        """Formatear recomendaciones de equipos"""
        
        response = "Basado en tus necesidades, te recomiendo:\n\n"
        
        for i, equipment in enumerate(recommendations, 1):
            response += f"**{i}. {equipment['name']}**\n"
            response += f"   • Altura máxima: {equipment['max_height']}m\n"
            response += f"   • Capacidad: {equipment['max_capacity']}kg\n"
            response += f"   • Precio por día: ${equipment['daily_rate']}\n\n"
        
        response += "¿Te gustaría que prepare una cotización con alguno de estos equipos?"
        
        return response
    
    def _format_quote_response(self, pricing_info: Dict, equipment: List[Dict]) -> str:
        """Formatear respuesta de cotización"""
        
        response = "🎯 **COTIZACIÓN**\n\n"
        
        response += "**Equipos:**\n"
        for item in equipment:
            response += f"• {item['name']} x{item['quantity']} - ${item['subtotal']}\n"
        
        response += f"\n**Resumen:**\n"
        response += f"• Subtotal equipos: ${pricing_info['equipment_subtotal']}\n"
        response += f"• Costo de entrega: ${pricing_info['delivery_cost']}\n"
        response += f"• Seguro: ${pricing_info['insurance_cost']}\n"
        response += f"• **Total: ${pricing_info['total_amount']}**\n\n"
        response += f"Cotización válida hasta: {pricing_info['valid_until'].strftime('%d/%m/%Y')}\n\n"
        response += "¿Te interesa proceder con esta cotización?"
        
        return response
    
    def _build_system_prompt(self, state: RentalAgentState) -> str:
        """Construir prompt del sistema para el LLM"""
        
        return f"""Eres un asistente especializado en alquiler de equipos de altura para {settings.company_name}.

Tu objetivo es ayudar al cliente de manera amigable y profesional. 

Información actual del cliente:
- Etapa de conversación: {state['conversation_stage']}
- Proyecto: {state['project_details'].project_type or 'No especificado'}
- Ubicación: {state['project_details'].location or 'No especificado'}

Mantén un tono conversacional, sé específico en tus respuestas y siempre busca avanzar hacia generar una cotización."""
    
    def _determine_next_action_from_response(self, state: RentalAgentState, response: str) -> str:
        """Determinar siguiente acción basada en la respuesta del LLM"""
        
        current_stage = state["conversation_stage"]
        
        # Mapeo simple basado en etapa actual
        stage_next_action = {
            "greeting": "information_gatherer",
            "gathering_basic_info": "information_gatherer",
            "gathering_technical_info": "equipment_advisor",
            "equipment_recommendation": "quote_calculator", 
            "quote_generation": "conversation_manager",
            "quote_review": "conversation_manager"
        }
        
        return stage_next_action.get(current_stage, "conversation_manager")
    
    def _add_message_to_history(self, state: RentalAgentState, role: str, content: str):
        """Agregar mensaje al historial de conversación"""
        
        message = ConversationMessage(
            role=role,
            content=content,
            timestamp=datetime.now(),
            message_type=None
        )
        
        state["conversation_history"].append(message)