from fastapi import FastAPI
from database import engine
import models

# Ye line tumhare naye kamre (router) ko import karti hai
from routers import businesses, users

# Godown mein Racks banayegi ye line
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="FBIP")

# JADOO KI LINE: Ye Receptionist ko batati hai ki Businesses wale department ka rasta kahan hai
app.include_router(businesses.router)
app.include_router(users.router)

# --- BASE ROUTES (Server check karne ke liye) ---
@app.get("/")
def read_root():
    return {"status": "ONLINE", "message": "Bhai server zinda hai, aur ab Enterprise level ka ho gaya hai!"}

@app.get("/api/v1/health")
def health_check():
    try:
        with engine.connect() as connection:
            return {"status": "HEALTHY", "database": "CONNECTED - Pipe jud gayi!"}
    except Exception as e:
        return {"status": "ERROR", "database": "FAILED", "details": str(e)}