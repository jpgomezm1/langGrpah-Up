from typing import Dict, List, Optional
from datetime import datetime
from src.agent.state import RentalAgentState, ConversationMessage, ClientInfo, ProjectDetails, EquipmentNeed, SiteConditions
from src.database.session import get_db_session, state_manager
from src.database.models import Customer, Conversation, Message
import uuid


class ConversationService:
    """Servicio para gestión de conversaciones"""
    
    def __init__(self):
        self.state_manager = state_manager
    
    def create_or_get_conversation(
        self, 
        telegram_user_id: str, 
        chat_id: str, 
        username: str = None
    ) -> RentalAgentState:
        """Crear o recuperar conversación existente"""
        
        with get_db_session() as db:
            # Buscar o crear cliente
            customer = db.query(Customer).filter(
                Customer.telegram_user_id == telegram_user_id
            ).first()
            
            if not customer:
                customer = Customer(
                    telegram_user_id=telegram_user_id,
                    username=username
                )
                db.add(customer)
                db.flush()
            else:
                # Actualizar última actividad
                customer.last_active = datetime.now()
            
            # Buscar conversación activa
            active_conversation = db.query(Conversation).filter(
                Conversation.customer_id == customer.id,
                Conversation.chat_id == chat_id,
                Conversation.ended_at.is_(None)
            ).order_by(Conversation.created_at.desc()).first()
            
            # Si no hay conversación activa o es muy antigua, crear nueva
            if not active_conversation or self._is_conversation_stale(active_conversation):
                conversation = Conversation(
                    customer_id=customer.id,
                    chat_id=chat_id,
                    stage="greeting"
                )
                db.add(conversation)
                db.flush()
                
                # Crear estado inicial
                initial_state = self._create_initial_state(
                    customer, conversation, telegram_user_id, chat_id
                )
            else:
                # Cargar estado existente
                conversation = active_conversation
                initial_state = self._load_conversation_state(conversation.id)
                
                if not initial_state:
                    # Si no se puede cargar el estado, crear uno nuevo
                    initial_state = self._create_initial_state(
                        customer, conversation, telegram_user_id, chat_id
                    )
            
            db.commit()
            return initial_state
    
    def _create_initial_state(
        self, 
        customer: Customer, 
        conversation: Conversation, 
        user_id: str, 
        chat_id: str
    ) -> RentalAgentState:
        """Crear estado inicial de conversación"""
        
        state = RentalAgentState(
            user_id=user_id,
            chat_id=chat_id,
            session_id=conversation.id,
            conversation_history=[],
            last_message="",
            client_info=ClientInfo(
                name=customer.name,
                phone=customer.phone,
                email=customer.email,
                company=customer.company
            ),
            project_details=ProjectDetails(),
            equipment_needs=[],
            site_conditions=SiteConditions(),
            selected_equipment=[],
            pricing_info={},
            conversation_stage="greeting",
            current_topic=None,
            pending_questions=[],
            missing_information=[],
            next_action=None,
            needs_human_intervention=False,
            escalation_reason=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            language="es"
        )
        
        return state
    
    def _load_conversation_state(self, conversation_id: str) -> Optional[RentalAgentState]:
        """Cargar estado de conversación desde Redis"""
        
        state_data = self.state_manager.load_state(conversation_id)
        
        if state_data:
            # Convertir datos deserializados de vuelta a objetos
            try:
                return self._deserialize_state(state_data)
            except Exception as e:
                print(f"Error deserializing state: {e}")
                return None
        
        return None
    
    def save_conversation_state(self, state: RentalAgentState) -> bool:
        """Guardar estado de conversación"""
        
        # Serializar estado
        serialized_state = self._serialize_state(state)
        
        # Guardar en Redis
        saved = self.state_manager.save_state(state["session_id"], serialized_state)
        
        # También actualizar información en la base de datos
        if saved:
            self._update_conversation_in_db(state)
        
        return saved
    
    def add_message_to_conversation(
        self, 
        conversation_id: str, 
        role: str, 
        content: str, 
        message_type: str = None,
        telegram_message_id: str = None
    ):
        """Agregar mensaje a la conversación en BD"""
        
        with get_db_session() as db:
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                message_type=message_type,
                telegram_message_id=telegram_message_id
            )
            db.add(message)
            db.commit()
    
    def end_conversation(self, conversation_id: str):
        """Finalizar conversación"""
        
        with get_db_session() as db:
            conversation = db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            if conversation:
                conversation.ended_at = datetime.now()
                db.commit()
        
        # Eliminar estado de Redis
        self.state_manager.delete_state(conversation_id)
    
    def get_conversation_history(
        self, 
        conversation_id: str, 
        limit: int = 50
    ) -> List[Dict]:
        """Obtener historial de conversación"""
        
        with get_db_session() as db:
            messages = db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.created_at.desc()).limit(limit).all()
            
            return [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "message_type": msg.message_type,
                    "created_at": msg.created_at
                }
                for msg in reversed(messages)
            ]
    
    def _is_conversation_stale(self, conversation: Conversation) -> bool:
        """Verificar si una conversación está obsoleta"""
        
        # Considerar obsoleta si tiene más de 24 horas sin actividad
        time_diff = datetime.now() - conversation.updated_at
        return time_diff.total_seconds() > 86400  # 24 horas
    
    def _serialize_state(self, state: RentalAgentState) -> Dict:
        """Serializar estado para almacenamiento"""
        
        # Convertir objetos complejos a diccionarios
        serialized = {}
        
        for key, value in state.items():
            if hasattr(value, '__dict__'):
                # Objeto con atributos - convertir a dict
                serialized[key] = value.__dict__ if hasattr(value, '__dict__') else value
            elif isinstance(value, datetime):
                # Fechas - convertir a string ISO
                serialized[key] = value.isoformat()
            elif isinstance(value, list):
                # Listas - procesar cada elemento
                serialized[key] = [
                    item.__dict__ if hasattr(item, '__dict__') else item 
                    for item in value
                ]
            else:
                serialized[key] = value
        
        return serialized
    
    def _deserialize_state(self, state_data: Dict) -> RentalAgentState:
        """Deserializar estado desde almacenamiento"""
        
        # Reconstruir objetos desde diccionarios
        deserialized = {}
        
        for key, value in state_data.items():
            if key in ['created_at', 'updated_at'] and isinstance(value, str):
                # Convertir fechas de string ISO a datetime
                deserialized[key] = datetime.fromisoformat(value)
            elif key == 'client_info' and isinstance(value, dict):
                deserialized[key] = ClientInfo(**value)
            elif key == 'project_details' and isinstance(value, dict):
                deserialized[key] = ProjectDetails(**value)
            elif key == 'site_conditions' and isinstance(value, dict):
                deserialized[key] = SiteConditions(**value)
            elif key == 'equipment_needs' and isinstance(value, list):
                deserialized[key] = [EquipmentNeed(**item) for item in value]
            elif key == 'conversation_history' and isinstance(value, list):
                deserialized[key] = [
                    ConversationMessage(**item) for item in value
                ]
            else:
                deserialized[key] = value
        
        return RentalAgentState(**deserialized)
    
    def _update_conversation_in_db(self, state: RentalAgentState):
        """Actualizar información de conversación en BD"""
        
        with get_db_session() as db:
            conversation = db.query(Conversation).filter(
                Conversation.id == state["session_id"]
            ).first()
            
            if conversation:
                conversation.stage = state["conversation_stage"]
                conversation.current_topic = state.get("current_topic")
                conversation.needs_human_intervention = state.get("needs_human_intervention", False)
                conversation.escalation_reason = state.get("escalation_reason")
                conversation.updated_at = datetime.now()
                
                # Actualizar datos del proyecto si existen
                if state["project_details"].__dict__:
                    conversation.project_data = state["project_details"].__dict__
                
                db.commit()