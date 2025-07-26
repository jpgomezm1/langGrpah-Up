import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError
from typing import Dict, Any
import logging

from config.settings import settings
from src.telegram.handlers import TelegramHandlers
from src.telegram.middleware import RateLimitMiddleware, LoggingMiddleware
from src.database.session import create_tables

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, settings.log_level.upper())
)
logger = logging.getLogger(__name__)


class RentalBot:
    """Bot principal de Telegram para alquiler de equipos"""
    
    def __init__(self):
        self.token = settings.telegram_bot_token
        self.application = None
        self.handlers = TelegramHandlers()
        self.rate_limiter = RateLimitMiddleware()
        self.logger_middleware = LoggingMiddleware()
    
    def create_application(self) -> Application:
        """Crear aplicación de Telegram"""
        
        # Crear aplicación
        application = Application.builder().token(self.token).build()
        
        # Agregar manejadores de comandos
        application.add_handler(
            CommandHandler("start", self.handlers.start_command)
        )
        application.add_handler(
            CommandHandler("help", self.handlers.help_command)
        )
        application.add_handler(
            CommandHandler("cotizar", self.handlers.quote_command)
        )
        application.add_handler(
            CommandHandler("catalogo", self.handlers.catalog_command)
        )
        application.add_handler(
            CommandHandler("contacto", self.handlers.contact_command)
        )
        application.add_handler(
            CommandHandler("reset", self.handlers.reset_command)
        )
        
        # Manejador principal de mensajes de texto
        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND, 
                self.handlers.handle_message
            )
        )
        
        # Manejador de mensajes no soportados
        application.add_handler(
            MessageHandler(
                ~filters.TEXT, 
                self.handlers.handle_unsupported_message
            )
        )
        
        # Manejador de errores
        application.add_error_handler(self.error_handler)
        
        self.application = application
        return application
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejador global de errores"""
        
        logger.error(f"Exception while handling an update: {context.error}")
        
        # Intentar enviar mensaje de error al usuario
        if update and update.effective_chat:
            try:
                await update.effective_chat.send_message(
                    "🔧 Ha ocurrido un error técnico. Por favor, intenta nuevamente o contacta a nuestro soporte."
                )
            except TelegramError:
                logger.error("Failed to send error message to user")
    
    async def setup_webhook(self, webhook_url: str, webhook_secret: str = None):
        """Configurar webhook para producción"""
        
        try:
            await self.application.bot.set_webhook(
                url=webhook_url,
                secret_token=webhook_secret,
                drop_pending_updates=True
            )
            logger.info(f"Webhook set to {webhook_url}")
        except TelegramError as e:
            logger.error(f"Failed to set webhook: {e}")
            raise
    
    async def start_polling(self):
        """Iniciar bot en modo polling (desarrollo)"""
        
        logger.info("Starting bot in polling mode...")
        
        try:
            # Crear tablas de BD si no existen
            create_tables()
            
            # Iniciar aplicación
            await self.application.initialize()
            await self.application.start()
            
            # Obtener información del bot
            bot_info = await self.application.bot.get_me()
            logger.info(f"Bot started: @{bot_info.username}")
            
            # Iniciar polling
            await self.application.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            )
            
            # Mantener el bot corriendo
            await self.application.updater.idle()
            
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            raise
        finally:
            # Cleanup
            await self.application.stop()
            await self.application.shutdown()
    
    async def stop(self):
        """Detener el bot"""
        
        if self.application:
            logger.info("Stopping bot...")
            await self.application.stop()
            await self.application.shutdown()
    
    def run_polling(self):
        """Ejecutar bot en modo polling (método síncrono)"""
        
        try:
            asyncio.run(self.start_polling())
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot crashed: {e}")
            raise


# Instancia global del bot
rental_bot = RentalBot()