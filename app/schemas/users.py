from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str | None
    is_active: bool
    is_admin: bool
    llm_provider: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    full_name: str | None = None
    llm_provider: str | None = None


class UsageResponse(BaseModel):
    tokens_input: int
    tokens_output: int
    cost_usd: Decimal
    created_at: datetime
    task_id: UUID | None

    model_config = {"from_attributes": True}


class MemoryEntryResponse(BaseModel):
    prompt: str
    result: str
    timestamp: datetime
