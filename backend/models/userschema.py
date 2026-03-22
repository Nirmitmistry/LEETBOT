from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email:    EmailStr
    username: str = Field(..., min_length=3, max_length=30)
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email:    EmailStr
    password: str


class UserResponse(BaseModel):
    user_id:              str
    email:                str
    username:             str
    solved_problems:      list[str] = []
    attempted_problems:   list[str] = []
    preferred_difficulty: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         UserResponse


class UpdateProfile(BaseModel):
    preferred_difficulty: str | None = Field(None, example="Medium")
    username:             str | None = Field(None, min_length=3, max_length=30)


class SessionCreateRequest(BaseModel):
    slug: str = Field(..., example="two-sum")
