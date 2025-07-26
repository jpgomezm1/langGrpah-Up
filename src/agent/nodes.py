from typing import Dict, List, Any, Optional
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
            temperature=0.1,  # Reducimos la temperatura para extracciones precisas
            api_key=settings.openai_api_key
        )
        self.equipment_service = EquipmentService()
        self.pricing_service = PricingService()
    
    def message_router(self, state: RentalAgentState) -> RentalAgentState:
        """Nodo para clasificar y rutear mensajes entrantes."""
        
        last_message = state["last_message"].lower()
        current_stage = state["conversation_stage"]
        
        quote_keywords = ["cotización", "cotizar", "precio", "costo", "alquiler", "rentar", "interesado"]
        technical_keywords = ["altura", "andamio", "plataforma", "escalera", "metros", "kg", "especificaciones"]
        contact_keywords = ["contacto", "teléfono", "email", "dirección"]
        
        next_action = None
        conversation_stage = current_stage

        # 1. Manejar intenciones explícitas primero
        if any(keyword in last_message for keyword in quote_keywords):
            next_action = "information_gatherer"
            conversation_stage = "gathering_basic_info"
        elif any(keyword in last_message for keyword in technical_keywords):
            next_action = "information_gatherer"  # Recopilar contexto antes de recomendar
            conversation_stage = "gathering_technical_info"
        elif any(keyword in last_message for keyword in contact_keywords):
            next_action = "conversation_manager"
        
        # 2. Manejar el flujo de la conversación si no se encontró una intención específica
        elif current_stage == "greeting":
            # Este es el primer mensaje real después de la bienvenida. Iniciar la recopilación de información.
            next_action = "information_gatherer"
            conversation_stage = "gathering_basic_info"
        
        # 3. Si no se determina una ruta, usar el mapeo de etapas como fallback
        if not next_action:
            stage_mapping = {
                "gathering_basic_info": "information_gatherer",
                "gathering_technical_info": "information_gatherer", 
                "equipment_recommendation": "equipment_advisor",
                "quote_generation": "quote_calculator",
                "quote_review": "conversation_manager"
            }
            next_action = stage_mapping.get(current_stage, "conversation_manager")
            
        # Actualizar el estado
        state["next_action"] = next_action
        state["conversation_stage"] = conversation_stage
        state["updated_at"] = datetime.now()
        
        return state
    
    # --- NUEVA FUNCIÓN AUXILIAR MEJORADA 1 ---
    def _extract_with_llm(self, info_to_extract: str, last_message: str) -> Optional[str]:
        """Usa el LLM para extraer una pieza específica de información de un mensaje."""
        
        system_prompt = f"""
Eres un experto en extracción de información. Tu tarea es analizar el mensaje del usuario y extraer el valor para el siguiente campo: '{info_to_extract}'.
Responde únicamente con el valor extraído. Si la información no está presente, responde exactamente con la palabra 'None'.

Ejemplo para 'project_type':
Mensaje de usuario: "es para mantenimiento de una fachada"
Tu respuesta: "mantenimiento"

Ejemplo para 'location':
Mensaje de usuario: "el trabajo es en medellín"
Tu respuesta: "medellín"

Ejemplo para 'duration':
Mensaje de usuario: "lo necesito por tres semanas"
Tu respuesta: "21"

Ejemplo para 'height':
Mensaje de usuario: "necesito llegar a 5 metros de altura"
Tu respuesta: "5"

Ejemplo para 'equipment_type':
Mensaje de usuario: "necesito un andamio móvil"
Tu respuesta: "andamio"

Ejemplo para 'surface_type':
Mensaje de usuario: "el piso es de concreto"
Tu respuesta: "concreto"
"""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=last_message)
        ]
        
        # Usamos .invoke() que es la forma recomendada
        response = self.llm.invoke(messages)
        extracted_value = response.content.strip()

        # Comprobación robusta de una respuesta nula
        if extracted_value.lower() == "none" or len(extracted_value) == 0:
            return None
            
        return extracted_value

    # --- NUEVA FUNCIÓN AUXILIAR MEJORADA 2 ---
    def _update_state_with_extraction(self, state: RentalAgentState, info_key: str, value: str):
        """Actualiza el estado anidado con la información extraída."""
        if info_key == "project_type":
            state["project_details"].project_type = value
        elif info_key == "location":
            state["project_details"].location = value
        elif info_key == "duration":
            # Intentar extraer solo el número de la respuesta
            days_match = re.search(r'\d+', value)
            if days_match:
                try:
                    state["project_details"].duration_days = int(days_match.group(0))
                except (ValueError, TypeError):
                    pass # Ignorar si la conversión falla
        elif info_key == "height":
            try:
                height = float(value)
                if not state["equipment_needs"]:
                    state["equipment_needs"] = [EquipmentNeed()]
                state["equipment_needs"][0].height_needed = height
            except (ValueError, TypeError):
                pass
        elif info_key == "equipment_type":
            if not state["equipment_needs"]:
                state["equipment_needs"] = [EquipmentNeed()]
            state["equipment_needs"][0].equipment_type = value
        elif info_key == "surface_type":
            if not state["site_conditions"]:
                state["site_conditions"] = SiteConditions()
            state["site_conditions"].surface_type = value

    # --- NUEVA FUNCIÓN AUXILIAR 3 ---
    def _extract_all_possible_info(self, state: RentalAgentState, message: str):
        """Extrae toda la información posible del mensaje usando múltiples métodos."""
        
        # Lista de todos los campos que podemos extraer
        fields_to_extract = ["project_type", "location", "duration", "height", "equipment_type", "surface_type"]
        
        # 1. Extracción con LLM para cada campo
        for field in fields_to_extract:
            extracted_value = self._extract_with_llm(field, message)
            if extracted_value:
                self._update_state_with_extraction(state, field, extracted_value)
        
        # 2. Ejecutar también la extracción por regex para datos estructurados
        self._extract_information_from_message(state, message)

    # --- FUNCIÓN MODIFICADA MEJORADA ---
    def information_gatherer(self, state: RentalAgentState) -> RentalAgentState:
        """Nodo para recopilar información faltante de forma inteligente."""
        
        last_message = state["last_message"]
        
        # NUEVA LÓGICA: Extraer toda la información posible del mensaje
        self._extract_all_possible_info(state, last_message)
        
        # Ahora verificar qué información aún falta
        missing_info = self._identify_missing_information(state)
        
        if missing_info:
            # Si aún falta información, hacer la siguiente pregunta
            question = self._generate_contextual_question(state, missing_info[0])
            response_message = question
            next_action = "information_gatherer"
        else:
            # Si ya no falta nada, avanzar a la siguiente etapa
            current_stage = state["conversation_stage"]
            if current_stage == "gathering_basic_info":
                response_message = "¡Perfecto! Ahora necesito algunos detalles técnicos para recomendarte el mejor equipo."
                state["conversation_stage"] = "gathering_technical_info"
                next_action = "information_gatherer" # Vuelve a este mismo nodo para empezar a pedir la info técnica
            else: # Asumimos que la etapa es gathering_technical_info
                response_message = "¡Excelente! Con esta información puedo recomendarte los equipos más adecuados."
                state["conversation_stage"] = "equipment_recommendation"
                next_action = "equipment_advisor"
    
        self._add_message_to_history(state, "assistant", response_message)
        state["next_action"] = next_action
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
        """Extraer información estructurada del mensaje usando regex"""
        
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
            if not state["site_conditions"] or not state["site_conditions"].surface_type:
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