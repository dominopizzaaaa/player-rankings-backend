from fastapi import Depends, HTTPException, status, Request, APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os

# 🔐 Load secrets from environment
SECRET_KEY = os.getenv("SECRET_KEY", "fallback_key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
ENV = os.getenv("ENV", "dev")

# 🔐 Load Admin Credentials Securely
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# ✅ Require admin creds in production
if not ADMIN_USERNAME or not ADMIN_PASSWORD:
    if ENV != "dev":
        raise RuntimeError("ADMIN_USERNAME and ADMIN_PASSWORD must be set in production")
    ADMIN_USERNAME = ADMIN_USERNAME or "admin"
    ADMIN_PASSWORD = ADMIN_PASSWORD or "password123"

# 🔐 Token auth config
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# 🔐 Token creation
def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ✅ Auth validators
async def is_admin(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("role") != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden: Admins only")
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login to change details")

def verify_admin(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username != ADMIN_USERNAME:
            raise HTTPException(status_code=403, detail="Admin access required")
        return username
    except JWTError:
        raise HTTPException(status_code=403, detail="Invalid token")

# 🚪 Auth endpoints
router = APIRouter()

@router.post("/token")
async def login_token(form_data: OAuth2PasswordRequestForm = Depends()):
    print("DEBUG: Login attempt with", form_data.username, form_data.password)
    if form_data.username != ADMIN_USERNAME or form_data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token_data = {
        "sub": form_data.username,
        "role": "admin"
    }
    token = create_access_token(token_data, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": token, "token_type": "bearer"}

@router.post("/login")
async def login(request: Request):
    credentials = await request.json()
    if credentials["username"] != ADMIN_USERNAME or credentials["password"] != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token_data = {
        "sub": credentials["username"],
        "role": "admin"
    }
    token = create_access_token(token_data, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": token, "token_type": "bearer"}

@router.get("/admin-only")
async def admin_dashboard(username: str = Depends(verify_admin)):
    return {"message": "Welcome, Admin!"}
