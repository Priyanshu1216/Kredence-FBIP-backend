from fastapi import FastAPI, Depends, HTTPException
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

# --- NAYA RASTA (GET BY ID): Kisi ek business ka data lane ke liye ---
@app.get("/api/v1/businesses/{business_id}", response_model=schemas.BusinessResponse)
def read_business(business_id: int, db: Session = Depends(get_db)):
    # Godown mein jao aur sirf wahi file dhundo jiski ID is number se match kare
    business = db.query(models.Business).filter(models.Business.id == business_id).first()
    
    # Agar wo ID godown mein hai hi nahi, toh Bouncer error dega
    if business is None:
        raise HTTPException(status_code=404, detail="Bhai, is ID ka koi business nahi mila!")
        
    return business

# --- NAYA RASTA (PUT): Kisi business ka data update karne ke liye ---
@app.put("/api/v1/businesses/{business_id}", response_model=schemas.BusinessResponse)
def update_business(business_id: int, business_data: schemas.BusinessCreate, db: Session = Depends(get_db)):
    # 1. Godown se purani file nikalo
    existing_business = db.query(models.Business).filter(models.Business.id == business_id).first()
    
    # Bouncer check: Agar us ID ka koi business hai hi nahi
    if existing_business is None:
        raise HTTPException(status_code=404, detail="Bhai, is ID ka koi business nahi mila!")
        
    # 2. Purani file mein naya data likh do (Overwrite)
    existing_business.name = business_data.name
    existing_business.fssai_number = business_data.fssai_number
    existing_business.is_verified = business_data.is_verified
    
    # 3. Godown mein wapas save (commit) kar do
    db.commit()
    db.refresh(existing_business)
    
    return existing_business

# --- NAYA RASTA (DELETE): Kisi business ka data hamesha ke liye mitane ke liye ---
@app.delete("/api/v1/businesses/{business_id}")
def delete_business(business_id: int, db: Session = Depends(get_db)):
    # 1. Godown se wo file nikalo
    business_to_delete = db.query(models.Business).filter(models.Business.id == business_id).first()
    
    # Bouncer check: Agar wo ID hai hi nahi
    if business_to_delete is None:
        raise HTTPException(status_code=404, detail="Bhai, is ID ka koi business nahi mila!")
        
    # 2. File ko kachre ke dabbe mein daal do (Delete kar do)
    db.delete(business_to_delete)
    
    # 3. Godown mein changes save (commit) karo
    db.commit()
    
    return {"status": "SUCCESS", "message": f"Business ID {business_id} hamesha ke liye delete ho gaya!"}