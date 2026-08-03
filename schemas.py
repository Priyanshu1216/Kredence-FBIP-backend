from pydantic import BaseModel, EmailStr
from typing import Optional, List

# 1. --- REVIEW SCHEMAS (Jo miss ho gaya tha!) ---
class ReviewBase(BaseModel):
    rating: int
    comment: str

class ReviewCreate(ReviewBase):
    pass

class ReviewResponse(ReviewBase):
    id: int
    business_id: int

    class Config:
        from_attributes = True


# 2. --- BUSINESS SCHEMAS ---
class BusinessBase(BaseModel):
    name: str
    category: str
    location: str
    fssai_number: Optional[str] = None  # Exact models.py wala naam
    is_verified: bool = False
    
    # Naye Premium Data Columns 👇
    phone_number: Optional[str] = None
    is_operational: bool = True

class BusinessCreate(BusinessBase):
    pass

class BusinessResponse(BusinessBase):
    id: int
    reviews: List[ReviewResponse] = []  # Ye dhaga API mein Businesses ke saath Reviews bhi dikhayega!

    class Config:
        from_attributes = True


# 3. --- USER SCHEMAS ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: Optional[str] = "user"

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    role: str

    class Config:
        from_attributes = True


# 4. --- TOKEN SCHEMAS ---
class Token(BaseModel):
    access_token: str
    token_type: str