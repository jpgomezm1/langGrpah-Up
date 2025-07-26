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
                "escalation_handler": "escalation_handler"
            }
        )
        
        workflow.add_conditional_edges(
            "information_gatherer",
            self._route_from_information_gatherer,
            {
                "information_gatherer": "information_gatherer",
                "equipment_advisor": "equipment_advisor",
                "conversation_manager": "conversation_manager",
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
        return state.get("next_action", "conversation_manager")
    
    def _route_from_information_gatherer(self, state: RentalAgentState) -> str:
        """Rutear desde information_gatherer"""
        next_action = state.get("next_action", "end")
        
        # Si necesita intervención humana, escalar
        if state.get("needs_human_intervention", False):
            return "escalation_handler"
        
        return next_action
    
    def _route_from_equipment_advisor(self, state: RentalAgentState) -> str:
        """Rutear desde equipment_advisor"""
        next_action = state.get("next_action", "end")
        
        # Si necesita intervención humana, escalar
        if state.get("needs_human_intervention", False):
            return "escalation_handler"
        
        return next_action
    
    def _route_from_quote_calculator(self, state: RentalAgentState) -> str:
        """Rutear desde quote_calculator"""
        return state.get("next_action", "conversation_manager")
    
    def _route_from_conversation_manager(self, state: RentalAgentState) -> str:
        """Rutear desde conversation_manager"""
        next_action = state.get("next_action", "end")
        
        # Verificar si necesita escalación
        if state.get("needs_human_intervention", False):
            return "escalation_handler"
        
        # Verificar si la conversación ha terminado
        if state.get("conversation_stage") == "completed":
            return "end"
        
        return next_action
    
    def _route_from_escalation_handler(self, state: RentalAgentState) -> str:
        """Rutear desde escalation_handler"""
        return state.get("next_action", "end")
    
    def process_message(self, state: RentalAgentState) -> RentalAgentState:
        """Procesar mensaje a través del grafo"""
        try:
            # Ejecutar el grafo
            result = self.graph.invoke(state)
            return result
        except Exception as e:
            print(f"Error processing message: {e}")
            # Estado de fallback
            state["needs_human_intervention"] = True
            state["escalation_reason"] = f"Technical error: {str(e)}"
            return state
    
    async def aprocess_message(self, state: RentalAgentState) -> RentalAgentState:
        """Procesar mensaje de forma asíncrona"""
        try:
            # Ejecutar el grafo de forma asíncrona
            result = await self.graph.ainvoke(state)
            return result
        except Exception as e:
            print(f"Error processing message: {e}")
            # Estado de fallback
            state["needs_human_intervention"] = True
            state["escalation_reason"] = f"Technical error: {str(e)}"
            return state
    
    def get_graph_visualization(self) -> str:
        """Obtener representación visual del grafo (para debugging)"""
        try:
            return self.graph.get_graph().print_ascii()
        except:
            return "Graph visualization not available"


# Instancia global del grafo
agent_graph = RentalAgentGraph()