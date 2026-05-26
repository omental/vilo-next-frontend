from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    organization_name: str
    organization_slug: str
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
