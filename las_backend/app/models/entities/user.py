from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    problems = relationship("Problem", back_populates="user", cascade="all, delete-orphan")
    model_cards = relationship("ModelCard", back_populates="user", cascade="all, delete-orphan")
    evolution_logs = relationship("EvolutionLog", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    practice_submissions = relationship("PracticeSubmission", back_populates="user", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="user", cascade="all, delete-orphan")


class Problem(Base):
    __tablename__ = "problems"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    associated_concepts = Column(JSON, default=list)
    status = Column(String(50), default="new")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="problems")
    responses = relationship("ProblemResponse", back_populates="problem", cascade="all, delete-orphan")
    learning_path = relationship("LearningPath", back_populates="problem", uselist=False, cascade="all, delete-orphan")


class ProblemResponse(Base):
    __tablename__ = "problem_responses"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    problem_id = Column(String(36), ForeignKey("problems.id"), nullable=False)
    user_response = Column(Text, nullable=False)
    system_feedback = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    problem = relationship("Problem", back_populates="responses")


class LearningPath(Base):
    __tablename__ = "learning_paths"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    problem_id = Column(String(36), ForeignKey("problems.id"), nullable=False, unique=True)
    path_data = Column(JSON)
    current_step = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    problem = relationship("Problem", back_populates="learning_path")


class ModelCard(Base):
    __tablename__ = "model_cards"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    title = Column(String(500), nullable=False)
    concept_maps = Column(JSON)
    user_notes = Column(Text)
    examples = Column(JSON, default=list)
    counter_examples = Column(JSON, default=list)
    migration_attempts = Column(JSON, default=list)
    version = Column(Integer, default=1)
    parent_id = Column(String(36), ForeignKey("model_cards.id"))
    embedding = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="model_cards")
    children = relationship("ModelCard", backref="parent", remote_side=[id])
    evolution_logs = relationship("EvolutionLog", back_populates="model_card")


class EvolutionLog(Base):
    __tablename__ = "evolution_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    model_id = Column(String(36), ForeignKey("model_cards.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    action_taken = Column(String(50))
    previous_version_id = Column(String(36), ForeignKey("model_cards.id"))
    reason_for_change = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    model_card = relationship("ModelCard", back_populates="evolution_logs")
    user = relationship("User", back_populates="evolution_logs")


class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    problem_id = Column(String(36), ForeignKey("problems.id"))
    title = Column(String(500))
    messages = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="conversations")
    messages_relation = relationship("ConversationMessage", back_populates="conversation", cascade="all, delete-orphan")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    message_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    conversation = relationship("Conversation", back_populates="messages_relation")


class PracticeTask(Base):
    __tablename__ = "practice_tasks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(500), nullable=False)
    description = Column(Text)
    model_card_id = Column(String(36), ForeignKey("model_cards.id"))
    task_type = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    submissions = relationship("PracticeSubmission", back_populates="practice_task")


class PracticeSubmission(Base):
    __tablename__ = "practice_submissions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    practice_task_id = Column(String(36), ForeignKey("practice_tasks.id"), nullable=False)
    solution = Column(Text, nullable=False)
    feedback = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="practice_submissions")
    practice_task = relationship("PracticeTask", back_populates="submissions")


class Review(Base):
    __tablename__ = "reviews"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    review_type = Column(String(50))
    period = Column(String(50))
    content = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="reviews")
