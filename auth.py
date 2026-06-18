import os
from fastapi import Request, HTTPException, status
import database
from supabase import Client

# Note: bcrypt and custom jwt functions are removed since Supabase handles this natively.

def get_current_user(request: Request):
    """
    Dependency to extract user from session cookie.
    Validates against Supabase Auth.
    Returns a dict with user data or None if not authenticated.
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
            
        user_data = {
            "id": user_response.user.id,
            "email": user_response.user.email,
            "name": user_response.user.user_metadata.get("name", "User")
        }
        return user_data
    except Exception as e:
        print(f"Auth error: {e}")
        return None

def verify_api_key(api_key: str):
    """
    Validates an API key against Supabase public.api_keys table and returns the user dict.
    Returns None if invalid.
    """
    if not api_key:
        return None
        
    supabase = database.get_supabase_client()
    if not supabase:
        return None
        
    try:
        # Check if API key exists and is active
        response = supabase.table("api_keys").select("user_id").eq("api_key", api_key).eq("is_active", True).execute()
        if not response.data or len(response.data) == 0:
            return None
            
        user_id = response.data[0]["user_id"]
        
        # We don't have direct access to auth.users from the service role easily in standard client without service key
        # For API key validation, we just need the user ID for downstream row level security or logic.
        return {"id": user_id, "name": "API User", "email": ""}
        
    except Exception as e:
        print(f"API Key validation error: {e}")
        return None
