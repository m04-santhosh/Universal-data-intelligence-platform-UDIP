import os
from supabase import create_client, Client

def get_supabase_client() -> Client | None:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        print("Missing Supabase configuration")
        return None

    try:
        return create_client(url, key)
    except Exception as e:
        print(f"Supabase initialization error: {e}")
        return None
