from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from database import engine, Base, SessionLocal
import models
import schemas

# Godown mein Racks banayegi ye line
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="FBIP")

# Ye function har baar Godown ka darwaza kholega aur band karega
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- PURANE RASTE (GET) ---
@app.get("/")
def read_root():
    return {"status": "ONLINE", "message": "Bhai server zinda ho gaya!"}

@app.get("/api/v1/health")
def health_check():
    try:
        with engine.connect() as connection:
            return {"status": "HEALTHY", "database": "CONNECTED - Pipe jud gayi!"}
    except Exception as e:
        return {"status": "ERROR", "database": "FAILED", "details": str(e)}

# --- NAYA RASTA (POST): Naya Business Add Karne Ke Liye ---
@app.post("/api/v1/businesses/", response_model=schemas.BusinessResponse)
def create_business(business: schemas.BusinessCreate, db: Session = Depends(get_db)):
    # 1. Bouncer (schemas) se verify hoke data yahan aaya
    # 2. Data ko Rack (models) format mein pack karo
    db_business = models.Business(name=business.name, fssai_number=business.fssai_number, is_verified=business.is_verified)
    
    # 3. Godown mein add karo aur Save (commit) karo
    db.add(db_business)
    db.commit()
    db.refresh(db_business) # Nayi ID nikalne ke liye refresh karo
    
    return db_business

# --- NAYA RASTA (GET ALL): Godown se saara data lane ke liye ---
@app.get("/api/v1/businesses/", response_model=list[schemas.BusinessResponse])
def read_businesses(db: Session = Depends(get_db)):
    # Godown mein jao aur saari businesses ki list utha lao
    businesses = db.query(models.Business).all()
    return businesses