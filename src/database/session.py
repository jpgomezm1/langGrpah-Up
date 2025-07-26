from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
from typing import Generator, Optional
import json
import httpx
import time
from config.settings import settings
from src.database.models import Base


# PostgreSQL Engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=settings.debug
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class UpstashRedisClient:
    """Cliente REST para Upstash Redis"""
    
    def __init__(self, url: str, token: str):
        self.url = url.rstrip('/')
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    
    async def _request(self, command: list):
        """Ejecutar comando Redis via REST API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.url,
                    headers=self.headers,
                    json=command,
                    timeout=10.0
                )
                if response.status_code == 200:
                    result = response.json()
                    return result.get('result')
                else:
                    print(f"Upstash error: {response.status_code} - {response.text}")
                    return None
        except Exception as e:
            print(f"Upstash request error: {e}")
            return None
    
    def _request_sync(self, command: list):
        """Ejecutar comando Redis via REST API (sincrónico)"""
        try:
            with httpx.Client() as client:
                response = client.post(
                    self.url,
                    headers=self.headers,
                    json=command,
                    timeout=10.0
                )
                if response.status_code == 200:
                    result = response.json()
                    return result.get('result')
                else:
                    print(f"Upstash error: {response.status_code} - {response.text}")
                    return None
        except Exception as e:
            print(f"Upstash request error: {e}")
            return None
    
    def ping(self):
        """Test connection"""
        result = self._request_sync(['PING'])
        return result == 'PONG'
    
    def get(self, key: str):
        """Get value"""
        return self._request_sync(['GET', key])
    
    def set(self, key: str, value: str):
        """Set value"""
        return self._request_sync(['SET', key, value])
    
    def setex(self, key: str, seconds: int, value: str):
        """Set value with expiration"""
        return self._request_sync(['SETEX', key, str(seconds), value])
    
    def delete(self, key: str):
        """Delete key"""
        result = self._request_sync(['DEL', key])
        return bool(result)
    
    def expire(self, key: str, seconds: int):
        """Set expiration"""
        result = self._request_sync(['EXPIRE', key, str(seconds)])
        return bool(result)
    
    def incr(self, key: str):
        """Increment key"""
        return self._request_sync(['INCR', key])


# Redis connection
redis_client = None
try:
    # Intentar usar Upstash si está configurado
    upstash_url = getattr(settings, 'upstash_redis_rest_url', None)
    upstash_token = getattr(settings, 'upstash_redis_rest_token', None)
    
    if upstash_url and upstash_token:
        redis_client = UpstashRedisClient(upstash_url, upstash_token)
        # Comentar temporalmente el ping para testing
        # if redis_client.ping():
        #     print("✅ Upstash Redis connected successfully")
        # else:
        #     print("⚠️ Upstash Redis ping failed")
        #     redis_client = None
        print("🔄 Upstash Redis configured (ping disabled for testing)")
    else:
        print("⚠️ Upstash Redis not configured")
        redis_client = None
        
except Exception as e:
    print(f"⚠️ Redis connection failed: {e}")
    print("🔄 Running without Redis (using memory-based fallback)")
    redis_client = None


def create_tables():
    """Crear todas las tablas en la base de datos"""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency para obtener sesión de base de datos"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager para sesiones de base de datos"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class StateManager:
    """Manejador de estado para conversaciones"""
    
    def __init__(self):
        self.redis = redis_client
        self.state_ttl = 3600 * 24  # 24 horas
        self.memory_cache = {}  # Fallback en memoria si Redis no está disponible
    
    def save_state(self, conversation_id: str, state: dict) -> bool:
        """Guardar estado en Redis o memoria"""
        try:
            if self.redis:
                state_key = f"conversation_state:{conversation_id}"
                serialized_state = json.dumps(state, default=str)
                return self.redis.setex(state_key, self.state_ttl, serialized_state)
            else:
                # Fallback a memoria
                self.memory_cache[conversation_id] = state
                return True
        except Exception as e:
            print(f"Error saving state: {e}")
            # Fallback a memoria
            self.memory_cache[conversation_id] = state
            return True
    
    def load_state(self, conversation_id: str) -> Optional[dict]:
        """Cargar estado desde Redis o memoria"""
        try:
            if self.redis:
                state_key = f"conversation_state:{conversation_id}"
                serialized_state = self.redis.get(state_key)
                if serialized_state:
                    return json.loads(serialized_state)
                return None
            else:
                # Fallback a memoria
                return self.memory_cache.get(conversation_id)
        except Exception as e:
            print(f"Error loading state: {e}")
            # Fallback a memoria
            return self.memory_cache.get(conversation_id)
    
    def delete_state(self, conversation_id: str) -> bool:
        """Eliminar estado de Redis o memoria"""
        try:
            if self.redis:
                state_key = f"conversation_state:{conversation_id}"
                return bool(self.redis.delete(state_key))
            else:
                # Fallback a memoria
                if conversation_id in self.memory_cache:
                    del self.memory_cache[conversation_id]
                    return True
                return False
        except Exception as e:
            print(f"Error deleting state: {e}")
            # Fallback a memoria
            if conversation_id in self.memory_cache:
                del self.memory_cache[conversation_id]
            return True
    
    def extend_state_ttl(self, conversation_id: str) -> bool:
        """Extender TTL del estado"""
        try:
            if self.redis:
                state_key = f"conversation_state:{conversation_id}"
                return self.redis.expire(state_key, self.state_ttl)
            else:
                # En memoria no necesita TTL
                return True
        except Exception as e:
            print(f"Error extending TTL: {e}")
            return True


class RateLimiter:
    """Rate limiter usando Redis o memoria"""
    
    def __init__(self):
        self.redis = redis_client
        self.memory_cache = {}  # Fallback en memoria
    
    def is_rate_limited(self, user_id: str) -> bool:
        """Verificar si el usuario está rate limited"""
        try:
            if self.redis:
                minute_key = f"rate_limit:{user_id}:minute"
                hour_key = f"rate_limit:{user_id}:hour"
                
                # Verificar límite por minuto
                minute_count = self.redis.get(minute_key)
                if minute_count and int(minute_count) >= settings.max_messages_per_minute:
                    return True
                
                # Verificar límite por hora
                hour_count = self.redis.get(hour_key)
                if hour_count and int(hour_count) >= settings.max_messages_per_hour:
                    return True
                
                return False
            else:
                # Fallback simple en memoria
                current_time = int(time.time())
                user_data = self.memory_cache.get(user_id, {"minute": 0, "hour": 0, "last_minute": 0, "last_hour": 0})
                
                # Reset contadores si ha pasado el tiempo
                if current_time - user_data["last_minute"] >= 60:
                    user_data["minute"] = 0
                    user_data["last_minute"] = current_time
                
                if current_time - user_data["last_hour"] >= 3600:
                    user_data["hour"] = 0
                    user_data["last_hour"] = current_time
                
                return (user_data["minute"] >= settings.max_messages_per_minute or 
                       user_data["hour"] >= settings.max_messages_per_hour)
        except Exception as e:
            print(f"Error checking rate limit: {e}")
            return False
    
    def increment_rate_limit(self, user_id: str):
        """Incrementar contadores de rate limit"""
        try:
            if self.redis:
                minute_key = f"rate_limit:{user_id}:minute"
                hour_key = f"rate_limit:{user_id}:hour"
                
                # Incrementar contador por minuto
                current_minute = self.redis.incr(minute_key)
                if current_minute == 1:
                    self.redis.expire(minute_key, 60)
                
                # Incrementar contador por hora
                current_hour = self.redis.incr(hour_key)
                if current_hour == 1:
                    self.redis.expire(hour_key, 3600)
            else:
                # Fallback en memoria
                current_time = int(time.time())
                if user_id not in self.memory_cache:
                    self.memory_cache[user_id] = {"minute": 0, "hour": 0, "last_minute": current_time, "last_hour": current_time}
                
                user_data = self.memory_cache[user_id]
                
                # Reset si ha pasado el tiempo
                if current_time - user_data["last_minute"] >= 60:
                    user_data["minute"] = 0
                    user_data["last_minute"] = current_time
                
                if current_time - user_data["last_hour"] >= 3600:
                    user_data["hour"] = 0
                    user_data["last_hour"] = current_time
                
                # Incrementar
                user_data["minute"] += 1
                user_data["hour"] += 1
        except Exception as e:
            print(f"Error incrementing rate limit: {e}")


# Instancias globales
state_manager = StateManager()
rate_limiter = RateLimiter()