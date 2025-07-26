from fastapi import FastAPI, Request, HTTPException, Header
from telegram import Update
import json
import asyncio
from typing import Optional

from config.settings import settings
from src.telegram.bot import rental_bot

app = FastAPI()

@app.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None)
):
    """Endpoint para recibir webhooks de Telegram"""
    
    # Verificar secret token si está configurado
    if settings.telegram_webhook_secret:
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            raise HTTPException(status_code=403, detail="Invalid secret token")
    
    try:
        # Obtener datos del webhook
        body = await request.body()
        update_data = json.loads(body.decode('utf-8'))
        
        # Crear objeto Update de Telegram
        update = Update.de_json(update_data, rental_bot.application.bot)
        
        # Procesar update de forma asíncrona
        await rental_bot.application.process_update(update)
        
        return {"status": "ok"}
        
    except Exception as e:
        print(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    """Endpoint de salud"""
    return {"status": "healthy", "service": "rental-bot"}