from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

# 1. Pehli Rack: Businesses
class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    fssai_number = Column(String, unique=True, index=True)
    is_verified = Column(Boolean, default=False)
    
    # Ye dhaga Businesses ko Reviews se jodta hai
    reviews = relationship("Review", back_populates="business")

# 2. Nayi Rack: Reviews
class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    rating = Column(Integer)                            # 1 se 5 star rating
    comment = Column(String)                            # Customer ka comment
    business_id = Column(Integer, ForeignKey("businesses.id")) # Ye asli "Kundi" (Foreign Key) hai jo Business se judti hai

    # Ye dhaga wapas Business ki taraf jata hai
    business = relationship("Business", back_populates="reviews")