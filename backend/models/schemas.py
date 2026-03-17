from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    ORGANIZER = "organizer"
    PARTICIPANT = "participant"
    REVIEWER = "reviewer"

class AppointmentType(str, Enum):
    PHYSICAL = "physical"
    VIDEO = "video"

class ParticipantStatus(str, Enum):
    INVITED = "invited"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELLED_BY_PARTICIPANT = "cancelled_by_participant"
    ON_TIME = "on_time"
    LATE = "late"
    NO_SHOW = "no_show"
    WAIVED = "waived"
    MANUAL_REVIEW = "manual_review"

class GuaranteeMode(str, Enum):
    SETUP_ONLY = "setup_only"
    AUTH_NOW = "auth_now"
    AUTH_LATER = "auth_later"

class GuaranteeStatus(str, Enum):
    NOT_STARTED = "not_started"
    AWAITING_PAYMENT_METHOD = "awaiting_payment_method"
    PENDING_ACTION = "pending_action"
    SETUP_COMPLETE = "setup_complete"
    AUTHORIZATION_ACTIVE = "authorization_active"
    AUTHORIZATION_EXPIRED = "authorization_expired"
    CAPTURE_REQUESTED = "capture_requested"
    CAPTURED = "captured"
    FAILED = "failed"
    RELEASED = "released"
    REFUNDED = "refunded"

class DisputeStatus(str, Enum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    REJECTED = "rejected"

class CalendarProvider(str, Enum):
    GOOGLE = "google"
    OUTLOOK = "outlook"
    ICS = "ics"

class SyncStatus(str, Enum):
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"
    DISCONNECTED = "disconnected"

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    user_id: str
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    is_verified: bool
    created_at: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordReset(BaseModel):
    token: str
    new_password: str

class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = None

class WorkspaceResponse(BaseModel):
    workspace_id: str
    name: str
    description: Optional[str] = None
    owner_id: str
    created_at: str

class ParticipantInput(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: str
    name: Optional[str] = None  # Kept for backward compatibility
    role: str = "participant"

class EventRemindersConfig(BaseModel):
    ten_minutes_before: bool = False
    one_hour_before: bool = False
    one_day_before: bool = False

class AppointmentCreate(BaseModel):
    workspace_id: str
    title: str
    appointment_type: AppointmentType
    location: Optional[str] = None
    meeting_provider: Optional[str] = None
    start_datetime: str
    duration_minutes: int
    tolerated_delay_minutes: int = 0
    cancellation_deadline_hours: int = 24
    penalty_amount: float
    penalty_currency: str = "eur"
    affected_compensation_percent: float = 70.0
    platform_commission_percent: float = 30.0
    charity_percent: float = 0.0
    policy_template_id: Optional[str] = None
    participants: Optional[List[ParticipantInput]] = []
    event_reminders: Optional[EventRemindersConfig] = None

class AppointmentResponse(BaseModel):
    appointment_id: str
    workspace_id: str
    organizer_id: str
    title: str
    appointment_type: str
    location: Optional[str] = None
    meeting_provider: Optional[str] = None
    start_datetime: str
    duration_minutes: int
    policy_snapshot_id: Optional[str] = None
    status: str
    created_at: str

class ParticipantAdd(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    role: str = "participant"

class AcceptanceCreate(BaseModel):
    appointment_id: str
    participant_id: str
    ip_address: str
    user_agent: str
    locale: str
    timezone: str

class PaymentGuaranteeCreate(BaseModel):
    participant_id: str
    appointment_id: str
    guarantee_mode: GuaranteeMode
    amount: float
    currency: str = "eur"

class DisputeCreate(BaseModel):
    violation_case_id: str
    participant_id: str
    reason: str
    description: str

class CalendarConnectionCreate(BaseModel):
    provider: CalendarProvider
    auth_code: Optional[str] = None