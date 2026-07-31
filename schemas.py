from pydantic import BaseModel

# --- 0. USERS KE BOUNCERS ---
class UserCreate(BaseModel):
    email: str
    password: str  # User apna asli password dega

class UserResponse(BaseModel):
    id: int
    email: str
    is_active: bool
    # Dhyan rahe: Hum response mein password wapas nahi bhejte (Security!)

    class Config:
        from_attributes = True

# --- 1. REVIEWS KE BOUNCERS (Naye wale) ---
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

# --- 2. BUSINESS KE BOUNCERS (Purane wale + Naya update) ---
class BusinessBase(BaseModel):
    name: str
    fssai_number: str
    is_verified: bool = False

class BusinessCreate(BusinessBase):
    pass

# Is aakhri bouncer mein humne 'reviews' wali line jodi hai
class BusinessResponse(BusinessBase):
    id: int
    reviews: list[ReviewResponse] = []  # Ye line business ke sath uske reviews layegi

    class Config:
        from_attributes = True

# --- 3. LOGIN KE BOUNCERS ---
class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str