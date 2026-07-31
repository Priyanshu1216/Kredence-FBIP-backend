from pydantic import BaseModel

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