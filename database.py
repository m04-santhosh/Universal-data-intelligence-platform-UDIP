import os
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_ANON_KEY")

print("SUPABASE_URL:", bool(SUPABASE_URL))
print("SUPABASE_KEY/ANON_KEY:", bool(SUPABASE_KEY))

try:
    _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
    print("SUPABASE CLIENT:", _supabase_client)
except Exception as e:
    _supabase_client = None
    print("SUPABASE CLIENT INIT ERROR:", str(e))

def get_supabase_client() -> Client | None:
    return _supabase_client
