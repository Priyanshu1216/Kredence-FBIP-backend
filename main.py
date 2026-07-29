from fastapi import FastAPI
from database import engine

app = FastAPI(title="FBIP")

@app.get("/")
def read_root():
    return {"status": "ONLINE", "message": "Bhai server zinda ho gaya!"}

@app.get("/api/v1/health")
def health_check():
    try:
        # Yahan hum Godown ke sath connection test kar rahe hain
        with engine.connect() as connection:
            return {"status": "HEALTHY", "database": "CONNECTED - Pipe jud gayi!"}
    except Exception as e:
        # Agar password ya kisi cheez mein galti hogi toh ye error batayega
        return {"status": "ERROR", "database": "FAILED", "details": str(e)}