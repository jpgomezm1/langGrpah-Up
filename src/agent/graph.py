from langgraph.graph import StateGraph, END
from typing import Dict, Any
from src.agent.state import RentalAgentState
from src.agent.nodes import AgentNodes


class RentalAgentGraph:
    """Construcción del grafo principal del agente"""
    
    def __init__(self):
        self.nodes = AgentNodes()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Construir el grafo de estados"""
        
        # Crear el grafo
        workflow = StateGraph(RentalAgentState)
        
        # Agregar nodos
        workflow.add_node("message_router", self.nodes.message_router)
        workflow.add_node("information_gatherer", self.nodes.information_gatherer)
        workflow.add_node("equipment_advisor", self.nodes.equipment_advisor)
        workflow.add_node("quote_calculator", self.nodes.quote_calculator)
        workflow.add_node("conversation_manager", self.nodes.conversation_manager)
        workflow.add_node("escalation_handler", self.nodes.escalation_handler)
        
        # Definir punto de entrada
        workflow.set_entry_point("message_router")
        
        # Agregar aristas condicionales
        workflow.add_conditional_edges(
            "message_router",
            self._route_from_router,
            {
                "information_gatherer": "information_gatherer",
                "equipment_advisor": "equipment_advisor",
                "quote_calculator": "quote_calculator",
                "conversation_manager": "conversation_manager",
                "escalation_handler": "escalation_handler",
                "end": END
            }
        )
        
        workflow.add_conditional_edges(
            "information_gatherer",
            self._route_from_information_gatherer,
            {
                "information_gatherer": "information_gatherer",
                "equipment_advisor": "equipment_advisor",
                "conversation_manager": "conversation_manager",
                # RUTA DE ESCAPE AÑADIDA
                "escalation_handler": "escalation_handler",
                "end": END
            }
        )
        
        workflow.add_conditional_edges(
            "equipment_advisor",
            self._route_from_equipment_advisor,
            {
                "quote_calculator": "quote_calculator",
                "escalation_handler": "escalation_handler",
                "conversation_manager": "conversation_manager",
                "end": END
            }
        )
        
        workflow.add_conditional_edges(
            "quote_calculator",
            self._route_from_quote_calculator,
            {
                "conversation_manager": "conversation_manager",
                # RUTA DE ESCAPE AÑADIDA
                "escalation_handler": "escalation_handler",
                "end": END
            }
        )
        
        workflow.add_conditional_edges(
            "conversation_manager",
            self._route_from_conversation_manager,
            {
                "information_gatherer": "information_gatherer",
                "equipment_advisor": "equipment_advisor", 
                "quote_calculator": "quote_calculator",
                "escalation_handler": "escalation_handler",
                "end": END
            }
        )
        
        workflow.add_conditional_edges(
            "escalation_handler",
            self._route_from_escalation_handler,
            {
                "conversation_manager": "conversation_manager",
                "end": END
            }
        )
        
        # Compilar el grafo
        return workflow.compile()
    
    def _route_from_router(self, state: RentalAgentState) -> str:
        """Rutear desde message_router"""
        next_action = state.get("next_action", "conversation_manager")
        
        # Verificar si necesita escalación desde el router
        if state.get("needs_human_intervention", False):
            return "escalation_handler"
        
        return next_action
    
    def _route_from_information_gatherer(self, state: RentalAgentState) -> str:
        """Rutear desde information_gatherer"""
        next_action = state.get("next_action", "end")  # Por defecto, terminar si no hay acción.
        
        # 👇 --- NUEVA LÓGICA DE ENRUTAMIENTO ---
        # Si la acción es 'end', terminamos el turno actual.
        if next_action == "end":
            return END
            
        # Si necesita intervención humana, escalar.
        if state.get("needs_human_intervention", False):
            return "escalation_handler"
            
        # Si la conversación está completada, terminar.
        if state.get("conversation_stage") == "completed":
            return END
            
        # De lo contrario, ir al nodo que 'next_action' especifica.
        return next_action
    
    def _route_from_equipment_advisor(self, state: RentalAgentState) -> str:
        """Rutear desde equipment_advisor"""
        next_action = state.get("next_action", "end")
        
        # Si la acción es 'end', terminamos el turno actual.
        if next_action == "end":
            return END
        
        # Si necesita intervención humana, escalar
        if state.get("needs_human_intervention", False):
            return "escalation_handler"
        
        # Verificar si la conversación ha terminado
        if state.get("conversation_stage") == "completed":
            return END
        
        return next_action
    
    def _route_from_quote_calculator(self, state: RentalAgentState) -> str:
        """Rutear desde quote_calculator"""
        next_action = state.get("next_action", "conversation_manager")
        
        # Si la acción es 'end', terminamos el turno actual.
        if next_action == "end":
            return END
        
        # Si necesita intervención humana, escalar
        if state.get("needs_human_intervention", False):
            return "escalation_handler"
        
        # Verificar si la conversación ha terminado
        if state.get("conversation_stage") == "completed":
            return END
        
        return next_action
    
    def _route_from_conversation_manager(self, state: RentalAgentState) -> str:
        """Rutear desde conversation_manager"""
        next_action = state.get("next_action", "end")
        
        # Si la acción es 'end', terminamos el turno actual.
        if next_action == "end":
            return END
        
        # Verificar si necesita escalación
        if state.get("needs_human_intervention", False):
            return "escalation_handler"
        
        # Verificar si la conversación ha terminado
        if state.get("conversation_stage") == "completed":
            return END
        
        return next_action
    
    def _route_from_escalation_handler(self, state: RentalAgentState) -> str:
        """
        Ruta desde el escalation_handler.
        Después de escalar, puede continuar conversando o terminar.
        """
        next_action = state.get("next_action", "end")
        
        # Si la acción es 'end', terminamos el turno actual.
        if next_action == "end":
            return END
        
        # Verificar si la conversación ha terminado
        if state.get("conversation_stage") == "completed" or state.get("conversation_stage") == "escalated":
            return END
        
        # Si aún hay conversación después de la escalación, continuar
        if next_action == "conversation_manager":
            return "conversation_manager"
        
        # Por defecto, terminar después de escalar
        return END
    
    def process_message(self, state: RentalAgentState) -> RentalAgentState:
        """Procesar mensaje a través del grafo"""
        try:
            # Validar estado antes de procesar
            if not self._validate_state(state):
                state["needs_human_intervention"] = True
                state["escalation_reason"] = "Invalid state structure"
                return state
            
            # Ejecutar el grafo
            result = self.graph.invoke(state)
            return result
        except Exception as e:
            print(f"Error processing message: {e}")
            # Estado de fallback más robusto
            state["needs_human_intervention"] = True
            state["escalation_reason"] = f"Technical error: {str(e)}"
            state["conversation_stage"] = "escalated"
            state["next_action"] = "end"
            return state
    
    async def aprocess_message(self, state: RentalAgentState) -> RentalAgentState:
        """Procesar mensaje de forma asíncrona"""
        try:
            # Validar estado antes de procesar
            if not self._validate_state(state):
                state["needs_human_intervention"] = True
                state["escalation_reason"] = "Invalid state structure"
                return state
            
            # Ejecutar el grafo de forma asíncrona
            result = await self.graph.ainvoke(state)
            return result
        except Exception as e:
            print(f"Error processing message: {e}")
            # Estado de fallback más robusto
            state["needs_human_intervention"] = True
            state["escalation_reason"] = f"Technical error: {str(e)}"
            state["conversation_stage"] = "escalated"
            state["next_action"] = "end"
            return state
    
    def _validate_state(self, state: RentalAgentState) -> bool:
        """Validar que el estado tenga la estructura mínima requerida"""
        try:
            # Verificar campos críticos
            required_fields = ["conversation_stage", "conversation_history", "last_message"]
            for field in required_fields:
                if field not in state:
                    print(f"Missing required field: {field}")
                    return False
            
            # Verificar que los objetos anidados existan
            if "project_details" not in state or state["project_details"] is None:
                print("Missing project_details")
                return False
            
            if "client_info" not in state or state["client_info"] is None:
                print("Missing client_info")
                return False
            
            return True
        except Exception as e:
            print(f"State validation error: {e}")
            return False
    
    def get_graph_visualization(self) -> str:
        """Obtener representación visual del grafo (para debugging)"""
        try:
            return self.graph.get_graph().print_ascii()
        except:
            return "Graph visualization not available"


# Instancia global del grafo
agent_graph = RentalAgentGraph()