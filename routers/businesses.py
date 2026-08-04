from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas, auth
from database import SessionLocal

# Ye FastAPI ka naya tool hai jo alag department banata hai
router = APIRouter(
    prefix="/api/v1/businesses", # Ab ye baar-baar har raste mein likhne ki zaroorat nahi
    tags=["Businesses"]          # Swagger UI mein saare raste is naam ke andar dikhenge
)

# Godown ka darwaza kholne wala function
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 1. CREATE BUSINESS
@router.post("/", response_model=schemas.BusinessResponse)
def create_business(business: schemas.BusinessCreate, db: Session = Depends(get_db)):
    db_business = models.Business(**business.dict())
    db.add(db_business)
    db.commit()
    db.refresh(db_business)
    return db_business

# 2. GET ALL BUSINESSES
@router.get("/", response_model=list[schemas.BusinessResponse])
def read_businesses(db: Session = Depends(get_db)):
    businesses = db.query(models.Business).all()
    return businesses

# 3. GET BUSINESS BY ID
@router.get("/{business_id}", response_model=schemas.BusinessResponse)
def read_business(business_id: int, db: Session = Depends(get_db)):
    business = db.query(models.Business).filter(models.Business.id == business_id).first()
    if business is None:
        raise HTTPException(status_code=404, detail="Bhai, is ID ka koi business nahi mila!")
    return business

# 4. UPDATE BUSINESS
@router.put("/{business_id}", response_model=schemas.BusinessResponse)
def update_business(business_id: int, business_data: schemas.BusinessCreate, db: Session = Depends(get_db)):
    existing_business = db.query(models.Business).filter(models.Business.id == business_id).first()
    if existing_business is None:
        raise HTTPException(status_code=404, detail="Bhai, is ID ka koi business nahi mila!")
    
    existing_business.name = business_data.name
    existing_business.fssai_number = business_data.fssai_number
    existing_business.is_verified = business_data.is_verified
    db.commit()
    db.refresh(existing_business)
    return existing_business

# 5. DELETE BUSINESS
@router.delete("/{business_id}")
def delete_business(business_id: int, db: Session = Depends(get_db), current_user: str = Depends(auth.get_current_user)):
    business_to_delete = db.query(models.Business).filter(models.Business.id == business_id).first()
    if business_to_delete is None:
        raise HTTPException(status_code=404, detail="Bhai, is ID ka koi business nahi mila!")
    db.delete(business_to_delete)
    db.commit()
    return {"status": "SUCCESS", "message": f"Business ID {business_id} hamesha ke liye delete ho gaya!"}

# 6. ADD REVIEW
@router.post("/{business_id}/reviews/", response_model=schemas.ReviewResponse)
def create_review_for_business(business_id: int, review: schemas.ReviewCreate, db: Session = Depends(get_db)):
    db_business = db.query(models.Business).filter(models.Business.id == business_id).first()
    if db_business is None:
        raise HTTPException(status_code=404, detail="Bhai, is ID ka koi business nahi mila, toh review kiska likhun?")
        
    db_review = models.Review(rating=review.rating, comment=review.comment, business_id=business_id)
    db.add(db_review)
    db.commit()
    db.refresh(db_review)
    return db_review