from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
import models, schemas, hashing, auth
from database import SessionLocal

# Naya VIP kamra (Router) Users ke liye
router = APIRouter(
    prefix="/api/v1/users",
    tags=["Users"]
)

# Godown ka darwaza kholne wala function
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# NAYA RASTA (POST): Naya account banane ke liye
@router.post("/", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    
    # 1. Check karo ki kya is email se pehle hi koi account bana hua hai?
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Bhai, is email se pehle hi account bana hua hai!")

    # 2. Asli password ko Hashing Machine se khufiya code mein badlo
    khufiya_password = hashing.hash_password(user.password)

    # 3. Naye user ka data pack karo (Asli password nahi, khufiya password dalenge)
    new_user = models.User(email=user.email, hashed_password=khufiya_password)
    
    # 4. Godown mein save (commit) karo
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user


# NAYA RASTA (POST): User ke Login karne ke liye (Taale / Bouncer ke sath)
@router.post("/login", response_model=schemas.Token)
def login(user_credentials: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    
    # Dhyaan rahe: OAuth2 (Swagger) mein email ko by-default 'username' bola jata hai
    user = db.query(models.User).filter(models.User.email == user_credentials.username).first()
    
    if not user:
        raise HTTPException(status_code=403, detail="Bhai, Email ya Password galat hai!")
        
    if not hashing.verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(status_code=403, detail="Bhai, Email ya Password galat hai!")
        
    access_token = auth.create_access_token(data={"sub": user.email})
    
    return {"access_token": access_token, "token_type": "bearer"}