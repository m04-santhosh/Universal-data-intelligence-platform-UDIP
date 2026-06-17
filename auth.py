import os
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
import jwt
from fastapi import Request, HTTPException, status
import database

# Secret key for JWT (in production, use environment variable)
SECRET_KEY = os.environ.get("SECRET_KEY", "your-secret-key-12345")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(request: Request):
    """
    Dependency to extract user from session cookie.
    Returns a dict with user data or None if not authenticated.
    """
    token = request.cookies.get("session")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            return None
            
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        if user is None:
            return None
            
        return dict(user)
    except jwt.ExpiredSignatureError:
        return None
    except jwt.PyJWTError:
        return None

def verify_api_key(api_key: str):
    """
    Validates an API key and returns the user dict.
    Returns None if invalid.
    """
    if not api_key:
        return None
        
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.name, u.email 
        FROM users u 
        JOIN api_keys a ON u.id = a.user_id 
        WHERE a.api_key = ? AND a.is_active = 1
    """, (api_key,))
    user = cursor.fetchone()
    conn.close()
    
    if user is None:
        return None
        
    return dict(user)
