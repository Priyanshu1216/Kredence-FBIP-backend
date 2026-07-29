from pydantic import BaseModel

# 1. Base Bouncer (Basic cheezein check karega)
class BusinessBase(BaseModel):
    name: str
    fssai_number: str
    is_verified: bool = False

# 2. Entry Bouncer (Jab naya business register hoga tab check karega)
class BusinessCreate(BusinessBase):
    pass

# 3. Exit Bouncer (Jab data Godown se bahar jayega, toh usme ID bhi jod dega)
class BusinessResponse(BusinessBase):
    id: int

    class Config:
        from_attributes = True