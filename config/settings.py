from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # OpenAI Configuration
    openai_api_key: str
    openai_model: str = "gpt-4-turbo-preview"
    
    # Telegram Configuration
    telegram_bot_token: str
    telegram_webhook_url: Optional[str] = None
    telegram_webhook_secret: Optional[str] = None
    
    # Database Configuration
    database_url: str
    test_database_url: Optional[str] = None
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"
    
    # Upstash Redis Configuration
    upstash_redis_rest_url: Optional[str] = None
    upstash_redis_rest_token: Optional[str] = None
    
    # Application Configuration
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    api_port: int = 8000
    
    # Business Configuration
    company_name: str = "RentalHeights Inc"
    support_email: str = "support@rentalheights.com"
    support_phone: str = "+1234567890"
    default_currency: str = "USD"
    
    # Rate Limiting
    max_messages_per_minute: int = 10
    max_messages_per_hour: int = 100
    
    # Pricing Configuration
    base_delivery_cost: float = 50.0
    cost_per_km: float = 2.5
    weekend_surcharge: float = 1.2
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()