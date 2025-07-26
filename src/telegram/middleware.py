from telegram import Update
from telegram.ext import ContextTypes
from typing import Callable, Any
import time
import logging
from functools import wraps

from src.database.session import rate_limiter
from config.settings import settings

logger = logging.getLogger(__name__)


class RateLimitMiddleware:
    """Middleware para control de rate limiting"""
    
    def __init__(self):
        self.rate_limiter = rate_limiter
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator para aplicar rate limiting"""
        
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = str(update.effective_user.id)
            
            # Verificar rate limit
            if self.rate_limiter.is_rate_limited(user_id):
                await update.message.reply_text(
                    "⏰ Has enviado muchos mensajes muy rápido. "
                    "Por favor espera un momento antes de continuar."
                )
                return
            
            # Incrementar contador
            self.rate_limiter.increment_rate_limit(user_id)
            
            # Ejecutar función original
            return await func(update, context, *args, **kwargs)
        
        return wrapper


class LoggingMiddleware:
    """Middleware para logging de mensajes"""
    
    def __init__(self):
        self.logger = logger
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator para logging"""
        
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            # Log información del mensaje
            user = update.effective_user
            chat = update.effective_chat
            message = update.message
            
            log_data = {
                "user_id": user.id,
                "username": user.username,
                "chat_id": chat.id,
                "chat_type": chat.type,
                "message_id": message.message_id if message else None,
                "text": message.text if message and message.text else None,
                "function": func.__name__
            }
            
            self.logger.info(f"Processing message: {log_data}")
            
            # Medir tiempo de ejecución
            start_time = time.time()
            
            try:
                # Ejecutar función
                result = await func(update, context, *args, **kwargs)
                
                # Log tiempo de respuesta
                execution_time = time.time() - start_time
                self.logger.info(
                    f"Message processed successfully in {execution_time:.2f}s "
                    f"for user {user.id}"
                )
                
                return result
                
            except Exception as e:
                # Log error
                execution_time = time.time() - start_time
                self.logger.error(
                    f"Error processing message after {execution_time:.2f}s "
                    f"for user {user.id}: {str(e)}"
                )
                raise
        
        return wrapper


class SecurityMiddleware:
    """Middleware para verificaciones de seguridad"""
    
    def __init__(self):
        self.blocked_users = set()  # En producción esto vendría de la BD
        self.suspicious_patterns = [
            "http://",
            "https://",
            "script",
            "<script>",
            "javascript:",
            "eval(",
            "exec("
        ]
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator para verificaciones de seguridad"""
        
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user = update.effective_user
            message = update.message
            
            # Verificar usuario bloqueado
            if user.id in self.blocked_users:
                logger.warning(f"Blocked user {user.id} attempted to send message")
                return
            
            # Verificar patrones sospechosos en el mensaje
            if message and message.text:
                text_lower = message.text.lower()
                for pattern in self.suspicious_patterns:
                    if pattern in text_lower:
                        logger.warning(
                            f"Suspicious pattern '{pattern}' detected from user {user.id}"
                        )
                        await update.message.reply_text(
                            "⚠️ Tu mensaje contiene contenido no permitido. "
                            "Por favor reformula tu consulta."
                        )
                        return
            
            # Verificar longitud del mensaje
            if message and message.text and len(message.text) > 2000:
                await update.message.reply_text(
                    "📝 Tu mensaje es muy largo. Por favor divide tu consulta en mensajes más cortos."
                )
                return
            
            # Ejecutar función original
            return await func(update, context, *args, **kwargs)
        
        return wrapper


class ConversationStateMiddleware:
    """Middleware para manejo de estado de conversación"""
    
    def __init__(self):
        self.active_conversations = {}
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator para manejo de estado"""
        
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = str(update.effective_user.id)
            chat_id = str(update.effective_chat.id)
            conversation_key = f"{user_id}:{chat_id}"
            
            # Verificar si hay una conversación activa
            if conversation_key in self.active_conversations:
                # Extender TTL de la conversación
                self.active_conversations[conversation_key] = time.time()
            else:
                # Registrar nueva conversación
                self.active_conversations[conversation_key] = time.time()
            
            # Limpiar conversaciones inactivas (más de 1 hora)
            current_time = time.time()
            inactive_conversations = [
                key for key, last_activity in self.active_conversations.items()
                if current_time - last_activity > 3600  # 1 hora
            ]
            
            for key in inactive_conversations:
                del self.active_conversations[key]
            
            # Ejecutar función original
            return await func(update, context, *args, **kwargs)
        
        return wrapper


# Decoradores compuestos para uso fácil
def apply_all_middleware(func: Callable) -> Callable:
    """Aplicar todos los middlewares"""
    func = RateLimitMiddleware()(func)
    func = LoggingMiddleware()(func)
    func = SecurityMiddleware()(func)
    func = ConversationStateMiddleware()(func)
    return func


def apply_basic_middleware(func: Callable) -> Callable:
    """Aplicar middlewares básicos (logging y rate limiting)"""
    func = RateLimitMiddleware()(func)
    func = LoggingMiddleware()(func)
    return func