from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str):
    return pwd_context.hash(password)

# NAYA FUNCTION: Ye user ke dale password aur godown ke khufiya password ko match karega
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)