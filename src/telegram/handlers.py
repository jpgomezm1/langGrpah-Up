from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from typing import Dict, Any
import logging

from src.agent.graph import agent_graph
from src.services.conversation_service import ConversationService
from src.services.equipment_service import EquipmentService
from src.database.session import rate_limiter
from src.utils.constants import SYSTEM_MESSAGES
from config.settings import settings

logger = logging.getLogger(__name__)


class TelegramHandlers:
    """Manejadores de mensajes de Telegram"""
    
    def __init__(self):
        self.conversation_service = ConversationService()
        self.equipment_service = EquipmentService()
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start"""
        
        user = update.effective_user
        chat_id = str(update.effective_chat.id)
        
        # Verificar rate limiting
        if rate_limiter.is_rate_limited(str(user.id)):
            await update.message.reply_text(
                "⏰ Has enviado muchos mensajes. Por favor espera un momento antes de continuar."
            )
            return
        
        # Incrementar contador de rate limiting
        rate_limiter.increment_rate_limit(str(user.id))
        
        # Crear o recuperar conversación
        state = self.conversation_service.create_or_get_conversation(
            telegram_user_id=str(user.id),
            chat_id=chat_id,
            username=user.username
        )
        
        # Mensaje de bienvenida
        welcome_message = SYSTEM_MESSAGES["greeting"].format(
            company_name=settings.company_name
        )
        
        # Teclado inline con opciones
        keyboard = [
            [
                InlineKeyboardButton("💰 Solicitar Cotización", callback_data="quote"),
                InlineKeyboardButton("📋 Ver Catálogo", callback_data="catalog")
            ],
            [
                InlineKeyboardButton("📞 Contacto", callback_data="contact"),
                InlineKeyboardButton("❓ Ayuda", callback_data="help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await update.message.reply_text(
                welcome_message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            # Agregar mensaje al historial
            self.conversation_service.add_message_to_conversation(
                conversation_id=state["session_id"],
                role="user",
                content="/start",
                telegram_message_id=str(update.message.message_id)
            )
            
        except TelegramError as e:
            logger.error(f"Error sending start message: {e}")
            await update.message.reply_text(
                "Ha ocurrido un error. Por favor intenta nuevamente."
            )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /help"""
        
        help_text = f"""
🤖 **Asistente de {settings.company_name}**

**Comandos disponibles:**
- `/start` - Iniciar conversación
- `/cotizar` - Solicitar cotización rápida
- `/catalogo` - Ver catálogo de equipos
- `/contacto` - Información de contacto
- `/reset` - Reiniciar conversación

**¿Cómo puedo ayudarte?**
- Cotizar equipos de altura
- Información técnica sobre equipos
- Consultar disponibilidad
- Programar visitas técnicas

**Equipos disponibles:**
- Andamios
- Plataformas elevadoras
- Escaleras industriales
- Grúas
- Montacargas

¡Escríbeme qué necesitas y te ayudo a encontrar la mejor solución! 😊
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def quote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /cotizar"""
        
        user = update.effective_user
        chat_id = str(update.effective_chat.id)
        
        # Crear conversación
        state = self.conversation_service.create_or_get_conversation(
            telegram_user_id=str(user.id),
            chat_id=chat_id,
            username=user.username
        )
        
        # Cambiar estado a recopilación de información
        state["conversation_stage"] = "gathering_basic_info"
        state["last_message"] = "Quiero una cotización"
        
        # Procesar a través del agente
        updated_state = await agent_graph.aprocess_message(state)
        
        # Obtener respuesta del agente
        if updated_state["conversation_history"]:
            last_message = updated_state["conversation_history"][-1]
            response_text = last_message["content"]
        else:
            response_text = "¡Perfecto! Vamos a preparar tu cotización. ¿Qué tipo de trabajo vas a realizar?"
        
        # Guardar estado
        self.conversation_service.save_conversation_state(updated_state)
        
        await update.message.reply_text(response_text)
    
    async def catalog_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /catalogo"""
        
        try:
            # Obtener catálogo de equipos
            catalog = self.equipment_service.get_equipment_catalog()
            
            if not catalog:
                await update.message.reply_text(
                    "No hay equipos disponibles en este momento. Contacta a nuestro equipo para más información."
                )
                return
            
            # Formatear catálogo
            catalog_text = "📋 **CATÁLOGO DE EQUIPOS**\n\n"
            
            equipment_types = {}
            for item in catalog:
                eq_type = item["equipment_type"]
                if eq_type not in equipment_types:
                    equipment_types[eq_type] = []
                equipment_types[eq_type].append(item)
            
            for eq_type, items in equipment_types.items():
                catalog_text += f"**{eq_type.replace('_', ' ').title()}:**\n"
                for item in items[:3]:  # Máximo 3 por categoría
                    catalog_text += f"• {item['name']} - Hasta {item['max_height']}m - ${item['daily_rate']}/día\n"
                catalog_text += "\n"
            
            catalog_text += "💬 Escribe el nombre del equipo que te interesa para más información."
            
            await update.message.reply_text(catalog_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error showing catalog: {e}")
            await update.message.reply_text(
                "Error al mostrar el catálogo. Por favor intenta nuevamente."
            )
    
    async def contact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /contacto"""
        
        contact_text = f"""
📞 **INFORMACIÓN DE CONTACTO**

**{settings.company_name}**

📱 Teléfono: {settings.support_phone}
📧 Email: {settings.support_email}

**Horarios de atención:**
🕒 Lunes a Viernes: 7:00 AM - 6:00 PM
🕒 Sábados: 8:00 AM - 4:00 PM
🕒 Domingos: Emergencias únicamente

**Servicios:**
- Alquiler de equipos de altura
- Asesoría técnica
- Instalación y mantenimiento
- Capacitación en seguridad

¡También puedes continuar chateando conmigo para cotizaciones y consultas! 😊
        """
        
        await update.message.reply_text(contact_text, parse_mode='Markdown')
    
    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /reset"""
        
        user = update.effective_user
        chat_id = str(update.effective_chat.id)
        
        # Finalizar conversación actual
        state = self.conversation_service.create_or_get_conversation(
            telegram_user_id=str(user.id),
            chat_id=chat_id,
            username=user.username
        )
        
        if state.get("session_id"):
            self.conversation_service.end_conversation(state["session_id"])
        
        await update.message.reply_text(
            "✅ Conversación reiniciada. ¡Hola de nuevo! ¿En qué puedo ayudarte?"
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejador principal de mensajes de texto"""
        
        user = update.effective_user
        chat_id = str(update.effective_chat.id)
        message_text = update.message.text
        
        # Verificar rate limiting
        if rate_limiter.is_rate_limited(str(user.id)):
            await update.message.reply_text(
                "⏰ Has enviado muchos mensajes. Por favor espera un momento."
            )
            return
        
        # Incrementar contador
        rate_limiter.increment_rate_limit(str(user.id))
        
        try:
            # Crear o recuperar conversación
            state = self.conversation_service.create_or_get_conversation(
                telegram_user_id=str(user.id),
                chat_id=chat_id,
                username=user.username
            )
            
            # Actualizar último mensaje
            state["last_message"] = message_text
            
            # Procesar mensaje a través del agente
            updated_state = await agent_graph.aprocess_message(state)
            
            # Obtener respuesta del agente
            if updated_state["conversation_history"]:
                last_message = updated_state["conversation_history"][-1]
                if last_message["role"] == "assistant":
                    response_text = last_message["content"]
                else:
                    response_text = "¿En qué más puedo ayudarte?"
            else:
                response_text = "¿Podrías repetir tu consulta?"
            
            # Guardar estado actualizado
            self.conversation_service.save_conversation_state(updated_state)
            
            # Agregar mensaje del usuario a la BD
            self.conversation_service.add_message_to_conversation(
                conversation_id=updated_state["session_id"],
                role="user",
                content=message_text,
                telegram_message_id=str(update.message.message_id)
            )
            
            # Enviar respuesta
            await update.message.reply_text(
                response_text,
                parse_mode='Markdown' if '*' in response_text or '_' in response_text else None
            )
            
            # Agregar respuesta del asistente a la BD
            self.conversation_service.add_message_to_conversation(
                conversation_id=updated_state["session_id"],
                role="assistant",
                content=response_text
            )
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await update.message.reply_text(
                "🔧 Ha ocurrido un error. Por favor intenta nuevamente o contacta a nuestro soporte."
            )
    
    async def handle_unsupported_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejador para mensajes no soportados (imágenes, documentos, etc.)"""
        
        await update.message.reply_text(
            "📝 Por el momento solo puedo procesar mensajes de texto. "
            "Si necesitas enviar imágenes o documentos, por favor contacta directamente a nuestro equipo:\n"
            f"📞 {settings.support_phone}\n"
            f"📧 {settings.support_email}"
        )