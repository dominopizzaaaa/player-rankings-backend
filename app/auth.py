from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os

# ✅ Get secrets from environment variables
SECRET_KEY = os.getenv("SECRET_KEY", "fallback_key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# ✅ Load Admin Credentials Securely
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password123")

# ✅ Fake Admin DB Example
fake_admin_db = {
    ADMIN_USERNAME: {"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD, "role": "admin"}
}

# ✅ Auth functions
def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def is_admin(token: str = Depends(oauth2_scheme)):
    print("🧠 is_admin() called")
    print(f"🔐 Raw token: {token}")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(f"✅ Decoded JWT payload: {payload}")

        if payload.get("role") != "admin":
            print("❌ Access denied: role is not admin")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden: Admins only")

        return payload
    except JWTError as e:
        print(f"❌ JWT decode error: {e}")
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

# ✅ Endpoints
from fastapi import APIRouter

router = APIRouter()

@router.post("/token")
async def login_token(form_data: OAuth2PasswordRequestForm = Depends()):
    print("DEBUG: Login attempt with", form_data.username, form_data.password)
    user = fake_admin_db.get(form_data.username)
    if not user or user["password"] != form_data.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token_data = {"sub": user["username"], "role": user["role"]}
    token = create_access_token(token_data, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": token, "token_type": "bearer"}

@router.post("/login")
async def login(request: Request):
    credentials = await request.json()
    if credentials["username"] != ADMIN_USERNAME or credentials["password"] != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": credentials["username"]}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": token, "token_type": "bearer"}

@router.get("/admin-only")
async def admin_dashboard(username: str = Depends(verify_admin)):
    return {"message": "Welcome, Admin!"}
