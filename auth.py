import jwt
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException

SECRET_KEY = "mera_super_secret_code_fbip_project_ke_liye"
ALGORITHM = "HS256"

# Ye Swagger UI ko batata hai ki Taala kholne ki chabi kahan se milegi
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/users/login")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# BOUNCER: Ye check karega ki chabi asli hai ya nakli
def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        # Chabi (Token) ko khol kar check karo
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Nakli chabi!")
        return email
    except Exception:
        raise HTTPException(status_code=401, detail="Chabi galat hai ya expire ho gayi!")