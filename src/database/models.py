from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid

Base = declarative_base()


class Equipment(Base):
    __tablename__ = "equipment"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False)
    equipment_type = Column(String(50), nullable=False)  # andamio, plataforma, etc.
    brand = Column(String(100))
    model = Column(String(100))
    
    # Especificaciones técnicas
    max_height = Column(Float)  # metros
    max_capacity = Column(Float)  # kg
    platform_size = Column(String(50))  # "2x1.5m"
    weight = Column(Float)  # kg del equipo
    
    # Información comercial
    daily_rate = Column(Float, nullable=False)
    weekly_rate = Column(Float)
    monthly_rate = Column(Float)
    damage_deposit = Column(Float)
    
    # Estado y disponibilidad
    is_available = Column(Boolean, default=True)
    quantity_total = Column(Integer, default=1)
    quantity_available = Column(Integer, default=1)
    
    # Metadatos
    description = Column(Text)
    specifications = Column(JSON)  # Specs adicionales en JSON
    image_urls = Column(JSON)  # URLs de imágenes
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relaciones
    bookings = relationship("Booking", back_populates="equipment")


class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    telegram_user_id = Column(String(50), unique=True, nullable=False)
    username = Column(String(100))
    
    # Información personal
    name = Column(String(200))
    phone = Column(String(20))
    email = Column(String(100))
    company = Column(String(200))
    
    # Preferencias
    language = Column(String(10), default="es")
    contact_preference = Column(String(20), default="telegram")
    
    # Metadatos
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_active = Column(DateTime, default=func.now())
    
    # Relaciones
    conversations = relationship("Conversation", back_populates="customer")
    quotes = relationship("Quote", back_populates="customer")


class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    chat_id = Column(String(50), nullable=False)
    
    # Estado de la conversación
    stage = Column(String(50), default="greeting")
    current_topic = Column(String(100))
    
    # Datos recopilados
    project_data = Column(JSON)  # Información del proyecto
    equipment_needs = Column(JSON)  # Necesidades de equipamiento
    site_conditions = Column(JSON)  # Condiciones del sitio
    
    # Control de flujo
    needs_human_intervention = Column(Boolean, default=False)
    escalation_reason = Column(String(200))
    
    # Metadatos
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    ended_at = Column(DateTime)
    
    # Relaciones
    customer = relationship("Customer", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation")
    quotes = relationship("Quote", back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    
    # Contenido del mensaje
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    message_type = Column(String(50))  # greeting, question, quote_request, etc.
    
    # Metadatos
    telegram_message_id = Column(String(50))
    created_at = Column(DateTime, default=func.now())
    
    # Relación
    conversation = relationship("Conversation", back_populates="messages")


class Quote(Base):
    __tablename__ = "quotes"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    conversation_id = Column(String, ForeignKey("conversations.id"))
    
    # Información del proyecto
    project_name = Column(String(200))
    project_location = Column(String(500))
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    duration_days = Column(Integer)
    
    # Información comercial
    equipment_items = Column(JSON)  # Lista de equipos cotizados
    subtotal = Column(Float)
    delivery_cost = Column(Float)
    setup_cost = Column(Float)
    insurance_cost = Column(Float)
    tax_amount = Column(Float)
    total_amount = Column(Float)
    currency = Column(String(10), default="USD")
    
    # Estado de la cotización
    status = Column(String(20), default="draft")  # draft, sent, accepted, rejected, expired
    valid_until = Column(DateTime)
    
    # Metadatos
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    sent_at = Column(DateTime)
    
    # Relaciones
    customer = relationship("Customer", back_populates="quotes")
    conversation = relationship("Conversation", back_populates="quotes")
    bookings = relationship("Booking", back_populates="quote")


class Booking(Base):
    __tablename__ = "bookings"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    quote_id = Column(String, ForeignKey("quotes.id"))
    equipment_id = Column(String, ForeignKey("equipment.id"), nullable=False)
    
    # Detalles de la reserva
    quantity = Column(Integer, default=1)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    delivery_address = Column(Text)
    
    # Estado
    status = Column(String(20), default="pending")  # pending, confirmed, delivered, returned, cancelled
    
    # Costos
    daily_rate = Column(Float)
    total_days = Column(Integer)
    total_amount = Column(Float)
    
    # Metadatos
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relaciones
    quote = relationship("Quote", back_populates="bookings")
    equipment = relationship("Equipment", back_populates="bookings")


class ConversationState(Base):
    """Tabla para persistir el estado completo de las conversaciones"""
    __tablename__ = "conversation_states"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id"), unique=True, nullable=False)
    
    # Estado serializado
    state_data = Column(JSON, nullable=False)  # Estado completo del agente
    
    # Metadatos
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # TTL para limpieza automática (en horas)
    expires_at = Column(DateTime)