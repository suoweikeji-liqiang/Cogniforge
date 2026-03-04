from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from app.core.database import Base
from app.core.config import get_settings
from app.core.vector import EmbeddingVector

settings = get_settings()


class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200))
    is_active = Column(Boolean, default=True)
    role = Column(String(20), default="user")  # "admin" or "user"
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
    embedding = Column(EmbeddingVector(settings.MODEL_CARD_EMBEDDING_DIMENSIONS))
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
    embedding = Column(EmbeddingVector(settings.MODEL_CARD_EMBEDDING_DIMENSIONS))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="model_cards")
    children = relationship("ModelCard", backref="parent", remote_side=[id])
    evolution_logs = relationship("EvolutionLog", back_populates="model_card", foreign_keys="EvolutionLog.model_id")


class EvolutionLog(Base):
    __tablename__ = "evolution_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    model_id = Column(String(36), ForeignKey("model_cards.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    action_taken = Column(String(50))
    previous_version_id = Column(String(36), ForeignKey("model_cards.id"))
    reason_for_change = Column(Text)
    snapshot = Column(JSON)  # Snapshot of model card state at this point
    created_at = Column(DateTime, default=datetime.utcnow)

    model_card = relationship("ModelCard", back_populates="evolution_logs", foreign_keys=[model_id])
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
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    model_card_id = Column(String(36), ForeignKey("model_cards.id"))
    task_type = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="practice_tasks")
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


class ReviewSchedule(Base):
    __tablename__ = "review_schedules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    model_card_id = Column(String(36), ForeignKey("model_cards.id"), nullable=False)
    ease_factor = Column(Integer, default=2500)
    interval_days = Column(Integer, default=1)
    repetitions = Column(Integer, default=0)
    next_review_at = Column(DateTime, nullable=False)
    last_reviewed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="review_schedules")
    model_card = relationship("ModelCard", backref="review_schedules")


class CognitiveChallenge(Base):
    __tablename__ = "cognitive_challenges"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    model_card_id = Column(String(36), ForeignKey("model_cards.id"))
    challenge_type = Column(String(50))
    question = Column(Text, nullable=False)
    context = Column(JSON)
    user_answer = Column(Text)
    ai_feedback = Column(Text)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="cognitive_challenges")
    model_card = relationship("ModelCard", backref="cognitive_challenges")


class ResourceLink(Base):
    __tablename__ = "resource_links"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    url = Column(Text, nullable=False)
    title = Column(String(500))
    link_type = Column(String(20), default="webpage")  # webpage, video
    ai_summary = Column(Text)
    status = Column(String(20), default="unread")  # unread, reading, completed
    embedding = Column(EmbeddingVector(settings.MODEL_CARD_EMBEDDING_DIMENSIONS))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", backref="resource_links")


class QuickNote(Base):
    __tablename__ = "quick_notes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    source = Column(String(20), default="text")  # text, voice
    tags = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="quick_notes")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    token = Column(String(100), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token = Column(String(2048), unique=True, nullable=False, index=True)
    token_type = Column(String(20), nullable=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class LoginThrottle(Base):
    __tablename__ = "login_throttles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scope_key = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True, index=True)
    client_ip = Column(String(100), nullable=True, index=True)
    failed_count = Column(Integer, default=0, nullable=False)
    window_started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    blocked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RetrievalEvent(Base):
    __tablename__ = "retrieval_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    source = Column(String(100), nullable=False, index=True)
    query = Column(Text, nullable=False)
    retrieval_context = Column(Text)
    items = Column(JSON, default=list)
    result_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", backref="retrieval_events")


class CogTestSession(Base):
    __tablename__ = "cog_test_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    concept = Column(String, nullable=False)
    model_card_id = Column(String(36), ForeignKey("model_cards.id"), nullable=True)
    status = Column(String(20), default="active")   # active | stopped | completed
    agent_mode = Column(String(20), default="guide_challenger")
    max_rounds = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    model_card = relationship("ModelCard", backref="cog_test_sessions")
    turns = relationship("CogTestTurn", back_populates="session", cascade="all, delete-orphan")
    blind_spots = relationship("CogTestBlindSpot", back_populates="session", cascade="all, delete-orphan")
    snapshots = relationship("CogTestSnapshot", back_populates="session", cascade="all, delete-orphan")


class CogTestTurn(Base):
    __tablename__ = "cog_test_turns"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("cog_test_sessions.id"), nullable=False)
    turn_index = Column(Integer, nullable=False)
    round_number = Column(Integer, nullable=False)
    role = Column(String(20), nullable=False)   # guide | challenger | user
    dialogue_text = Column(Text, nullable=False)
    analysis_json = Column(Text, nullable=True)
    understanding_level = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("CogTestSession", back_populates="turns")
    blind_spots = relationship("CogTestBlindSpot", back_populates="turn")


class CogTestBlindSpot(Base):
    __tablename__ = "cog_test_blind_spots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("cog_test_sessions.id"), nullable=False)
    turn_id = Column(String, ForeignKey("cog_test_turns.id"), nullable=False)
    category = Column(String(20), nullable=False)   # gap | understood | unclear
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("CogTestSession", back_populates="blind_spots")
    turn = relationship("CogTestTurn", back_populates="blind_spots")


class CogTestSnapshot(Base):
    __tablename__ = "cog_test_snapshots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("cog_test_sessions.id"), nullable=False)
    round_number = Column(Integer, nullable=True)   # None = final session snapshot
    understanding_score = Column(String(10), nullable=True)   # stored as "0.72"
    blind_spot_count = Column(Integer, default=0)
    snapshot_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("CogTestSession", back_populates="snapshots")
