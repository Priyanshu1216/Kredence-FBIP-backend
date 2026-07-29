from sqlalchemy import Column, Integer, String, Boolean
from database import Base

# Ye humari pehli rack (Table) ka design hai
class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)          # Business ka Serial Number
    name = Column(String, index=True)                           # Business/Restaurant ka Naam
    fssai_number = Column(String, unique=True, index=True)      # FSSAI License Number (Unique hoga)
    is_verified = Column(Boolean, default=False)                # Kya ye verify ho chuka hai? (True/False)