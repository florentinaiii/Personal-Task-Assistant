from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=func.now())
    
    # Relationship to tasks
    tasks = relationship("Task", back_populates="user")

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    deadline = Column(DateTime, nullable=True)
    priority = Column(Integer, default=1)  # 1=low, 2=medium, 3=high
    status = Column(String(20), default="pending")  # pending, in_progress, completed
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    estimated_duration = Column(Float, nullable=True)  # in hours
    category = Column(String(100), nullable=True)
    is_recurring = Column(Boolean, default=False)
    recurring_pattern = Column(String(50), nullable=True)  # daily, weekly, monthly
    
    # Foreign key to user
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Email reminder fields
    notification_type = Column(String(20), default="websocket")  # email, websocket
    recipient_email = Column(String(255), nullable=True)  # Keep for backward compatibility
    reminder_minutes_before = Column(Integer, nullable=True)  # e.g., 60 for 1 hour before
    email_sent = Column(Boolean, default=False)
    
    # Relationship to user
    user = relationship("User", back_populates="tasks")

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    priority: Optional[int] = 1
    category: Optional[str] = None
    estimated_duration: Optional[float] = None
    reminder_time: Optional[datetime] = None
    notification_type: Optional[str] = "websocket"
    recipient_email: Optional[str] = None
    reminder_minutes_before: Optional[int] = None
    is_recurring: Optional[bool] = False
    recurring_pattern: Optional[str] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    category: Optional[str] = None
    estimated_duration: Optional[float] = None
    notification_type: Optional[str] = None
    recipient_email: Optional[str] = None
    reminder_minutes_before: Optional[int] = None
    email_sent: Optional[bool] = None
    is_recurring: Optional[bool] = None
    recurring_pattern: Optional[str] = None

class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    deadline: Optional[datetime]
    priority: int
    status: str
    created_at: datetime
    updated_at: datetime
    estimated_duration: Optional[float]
    category: Optional[str]
    notification_type: Optional[str]
    recipient_email: Optional[str]
    reminder_minutes_before: Optional[int]
    email_sent: Optional[bool]
    user_id: int
    is_recurring: Optional[bool]
    recurring_pattern: Optional[str]
    
    class Config:
        from_attributes = True

class ChatMessage(BaseModel):
    message: str
    user_email: Optional[str] = None

class MeetingRequest(BaseModel):
    title: str
    duration_hours: float = 1.0
    participants: Optional[List[str]] = None
    urgency: str = "normal"
    preferred_days: Optional[List[int]] = None
    preferred_time_start: Optional[int] = None
    preferred_time_end: Optional[int] = None
    days_ahead: int = 14

class UserLoginRequest(BaseModel):
    email: str

class UserResponse(BaseModel):
    id: int
    email: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class ChatResponse(BaseModel):
    response: str
    tasks_created: Optional[List[TaskResponse]] = []
    tasks_updated: Optional[List[TaskResponse]] = []
