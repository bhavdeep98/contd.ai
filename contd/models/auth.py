from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum

class UserRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserInDB(UserBase):
    user_id: UUID
    password_hash: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class User(UserBase):
    user_id: UUID
    created_at: datetime

    class Config:
        orm_mode = True

class OrganizationBase(BaseModel):
    name: str

class OrganizationCreate(OrganizationBase):
    pass

class Organization(OrganizationBase):
    org_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class OrganizationMemberBase(BaseModel):
    role: UserRole

class OrganizationMemberCreate(OrganizationMemberBase):
    user_email: EmailStr # Invite by email

class OrganizationMember(OrganizationMemberBase):
    org_id: UUID
    user_id: UUID
    joined_at: datetime

class ApiKeyCreate(BaseModel):
    name: str
    scopes: List[str] = []
    expires_in_days: Optional[int] = None

class ApiKey(BaseModel):
    key_id: UUID
    key_prefix: str
    org_id: UUID
    user_id: Optional[UUID]
    name: str
    scopes: List[str]
    created_at: datetime
    expires_at: Optional[datetime]

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[str] = None
    org_id: Optional[str] = None
