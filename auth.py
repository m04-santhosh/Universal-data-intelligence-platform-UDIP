import os
from fastapi import Request
import database

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

def get_current_user(request: Request):
    """
    Validates the session cookie JWT using Supabase.
    """
    token = request.cookies.get("session")
    if not token:
        return None
        
    supabase = database.get_supabase_client()
    if not supabase:
        return None
        
    try:
        user_response = supabase.auth.get_user(token)
        if not user_response or not user_response.user:
            return None
            
        return {
            "id": user_response.user.id,
            "email": user_response.user.email,
            "name": user_response.user.user_metadata.get("name", "User") if user_response.user.user_metadata else "User"
        }
    except Exception as e:
        print(f"Auth error: {e}")
        return None

def verify_api_key(api_key: str):
    """
    Validates an API key against Supabase using the Service Role Key (bypassing RLS).
    """
    if not api_key:
        return None
        
    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not service_key:
        print("Missing SUPABASE_SERVICE_ROLE_KEY for API validation")
        return None
        
    from supabase import create_client
    try:
        supabase_admin = create_client(url, service_key)
        response = supabase_admin.table("api_keys").select("user_id").eq("api_key", api_key).eq("is_active", True).execute()
        
        if not response.data:
            return None
            
        user_id = response.data[0]["user_id"]
        return {"id": user_id, "name": "API User", "email": ""}
    except Exception as e:
        print(f"API Key validation error: {e}")
        return None
