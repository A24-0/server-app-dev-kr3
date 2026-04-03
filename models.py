from typing import Literal

from pydantic import BaseModel, Field


class UserBase(BaseModel):
    username: str


class User(UserBase):
    password: str


class UserInDB(UserBase):
    hashed_password: str


class UserRegister(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    role: Literal["admin", "user", "guest"] = "guest"


class LoginJSON(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TodoCreate(BaseModel):
    title: str
    description: str


class TodoUpdate(BaseModel):
    title: str
    description: str
    completed: bool


class TodoOut(BaseModel):
    id: int
    title: str
    description: str
    completed: bool
