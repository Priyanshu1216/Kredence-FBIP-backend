from database import engine, Base
import models

print("Puraani tables hata rahe hain...")
Base.metadata.drop_all(bind=engine)

print("Nayi tables (updated columns ke sath) bana rahe hain...")
Base.metadata.create_all(bind=engine)

print("Database ekdum fresh aur ready hai! ✅")