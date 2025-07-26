#!/usr/bin/env python3
"""
Punto de entrada principal para el bot de alquiler de equipos de altura
"""

import asyncio
import sys
import signal
import logging
import uvicorn
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Header
from telegram import Update
import json
from typing import Optional

# Agregar el directorio src al path
sys.path.append(str(Path(__file__).parent))

from config.settings import settings
from src.telegram.bot import rental_bot
from src.database.session import create_tables
from src.utils.helpers import setup_logging, load_initial_data, health_check

logger = logging.getLogger(__name__)

# Crear aplicación FastAPI para webhooks
webhook_app = FastAPI(title="Rental Height Agent Bot", version="1.0.0")

@webhook_app.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None)
):
    """Endpoint para recibir webhooks de Telegram"""
    
    # Verificar secret token si está configurado
    if settings.telegram_webhook_secret:
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            logger.warning("Invalid webhook secret token received")
            raise HTTPException(status_code=403, detail="Invalid secret token")
    
    try:
        # Obtener datos del webhook
        body = await request.body()
        update_data = json.loads(body.decode('utf-8'))
        
        logger.info(f"Received webhook update: {update_data.get('update_id', 'unknown')}")
        
        # Crear objeto Update de Telegram
        update = Update.de_json(update_data, rental_bot.application.bot)
        
        # Procesar update de forma asíncrona
        await rental_bot.application.process_update(update)
        
        return {"status": "ok"}
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@webhook_app.get("/health")
async def health_endpoint():
    """Endpoint de verificación de salud"""
    health_status = await health_check()
    return health_status

@webhook_app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "service": "Rental Height Agent Bot",
        "status": "running",
        "version": "1.0.0",
        "webhook_configured": bool(settings.telegram_webhook_url)
    }


class Application:
    """Aplicación principal"""
    
    def __init__(self):
        self.bot = rental_bot
        self.running = False
        self.webhook_app = webhook_app
        self.server = None
    
    async def startup(self):
        """Inicialización de la aplicación"""
        
        logger.info("Starting Rental Height Agent Bot...")
        
        try:
            # Configurar logging
            setup_logging()
            
            # Crear tablas de base de datos
            logger.info("Creating database tables...")
            create_tables()
            
            # Cargar datos iniciales
            logger.info("Loading initial data...")
            await load_initial_data()
            
            # Crear aplicación del bot
            logger.info("Creating bot application...")
            self.bot.create_application()
            
            logger.info("Application startup completed successfully")
            
        except Exception as e:
            logger.error(f"Error during startup: {e}")
            raise
    
    async def setup_webhook_mode(self):
        """Configurar modo webhook"""
        
        try:
            logger.info(f"Setting up webhook: {settings.telegram_webhook_url}")
            
            # Configurar webhook en Telegram
            await self.bot.setup_webhook(
                settings.telegram_webhook_url,
                settings.telegram_webhook_secret
            )
            
            # Inicializar la aplicación del bot para webhooks
            await self.bot.application.initialize()
            
            logger.info("Webhook configured successfully")
            
        except Exception as e:
            logger.error(f"Error setting up webhook: {e}")
            raise
    
    async def start_webhook_server(self):
        """Iniciar servidor FastAPI para webhooks"""
        
        config = uvicorn.Config(
            self.webhook_app,
            host="0.0.0.0",
            port=settings.api_port,
            log_level="info",
            access_log=True,
            reload=settings.debug
        )
        
        self.server = uvicorn.Server(config)
        
        logger.info(f"Starting webhook server on port {settings.api_port}")
        await self.server.serve()
    
    async def run(self):
        """Ejecutar la aplicación"""
        
        self.running = True
        
        try:
            await self.startup()
            
            # Determinar modo de ejecución
            use_webhook = (
                settings.telegram_webhook_url and 
                (settings.environment == "production" or settings.environment == "development")
            )
            
            if use_webhook:
                # Modo webhook
                logger.info("Running in webhook mode...")
                
                # Configurar webhook
                await self.setup_webhook_mode()
                
                # Iniciar servidor FastAPI
                await self.start_webhook_server()
                
            else:
                # Modo polling
                logger.info("Running in polling mode...")
                await self.bot.start_polling()
                
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Error running application: {e}")
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Limpieza al cerrar la aplicación"""
        
        logger.info("Shutting down application...")
        self.running = False
        
        try:
            # Detener servidor FastAPI si existe
            if self.server:
                logger.info("Stopping webhook server...")
                self.server.should_exit = True
            
            # Detener el bot
            logger.info("Stopping Telegram bot...")
            await self.bot.stop()
            
            # Eliminar webhook si estaba configurado
            if settings.telegram_webhook_url and self.bot.application:
                try:
                    logger.info("Removing webhook...")
                    await self.bot.application.bot.delete_webhook()
                except Exception as e:
                    logger.warning(f"Error removing webhook: {e}")
            
            logger.info("Bot stopped successfully")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    def handle_signal(self, signum, frame):
        """Manejador de señales del sistema"""
        
        logger.info(f"Received signal {signum}")
        self.running = False
        
        # Para webhook mode, detener el servidor
        if self.server:
            self.server.should_exit = True


def main():
    """Función principal"""
    
    # Mostrar información de configuración
    print(f"🤖 Rental Height Agent Bot")
    print(f"Environment: {settings.environment}")
    print(f"Debug mode: {settings.debug}")
    print(f"API Port: {settings.api_port}")
    
    if settings.telegram_webhook_url:
        print(f"Webhook URL: {settings.telegram_webhook_url}")
        print(f"Mode: Webhook")
    else:
        print(f"Mode: Polling")
    
    print("-" * 50)
    
    app = Application()
    
    # Configurar manejadores de señales
    signal.signal(signal.SIGINT, app.handle_signal)
    signal.signal(signal.SIGTERM, app.handle_signal)
    
    try:
        # Ejecutar aplicación
        asyncio.run(app.run())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        logger.exception("Fatal error occurred")
        sys.exit(1)


if __name__ == "__main__":
    main()