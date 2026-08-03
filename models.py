from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

# 1. Pehli Rack: Businesses
class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    category = Column(String, index=True)
    location = Column(String)
    
    fssai_number = Column(String, unique=True, index=True, nullable=True) # FSSAI column
    is_verified = Column(Boolean, default=False)
    
    # Naye Premium Data Columns 👇
    phone_number = Column(String, nullable=True)
    is_operational = Column(Boolean, default=True)

    # Ye dhaga Businesses ko Reviews se jodta hai
    reviews = relationship("Review", back_populates="business")

# 2. Nayi Rack: Reviews (Jo miss ho gaya tha!)
class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    rating = Column(Integer)             # 1 se 5 star rating
    comment = Column(String)             # Customer ka comment
    business_id = Column(Integer, ForeignKey("businesses.id")) # Ye asli "Kundi" (Foreign Key) hai

    # Ye dhaga wapas Business ki taraf jata hai
    business = relationship("Business", back_populates="reviews")

# 3. Nayi Rack: Users (Login karne walon ke liye)
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)      # Asli password nahi, khufiya password
    is_active = Column(Boolean, default=True)
    role = Column(String, default="user") # Taala aur security (RBAC) ke liye