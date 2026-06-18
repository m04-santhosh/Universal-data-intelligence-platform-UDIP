import re

with open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replacement 1: Template Matching (lines 553-557 & 1238-1242 approx)
old_1 = """        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT template_id, template_name, mapping_json FROM mapping_templates WHERE user_id = ?", (user["id"],))
        templates = cursor.fetchall()
        conn.close()"""
new_1 = """        supabase = database.get_supabase_client()
        templates = []
        if supabase:
            res = supabase.table("mapping_templates").select("template_id, template_name, mapping_json").eq("user_id", user["id"]).execute()
            templates = res.data"""
content = content.replace(old_1, new_1)

# Replacement 2: Developer API Keys routes
old_api_keys = """@app.get("/api/keys")
async def get_api_keys(request: Request):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized"})
        
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM api_keys WHERE user_id = ? AND is_active = 1", (user["id"],))
    keys = cursor.fetchall()
    
    cursor.execute("SELECT * FROM automation_rules WHERE user_id = ?", (user["id"],))
    rules = cursor.fetchall()
    conn.close()
    
    return {
        "success": True, 
        "keys": [dict(k) for k in keys],
        "rules": [dict(r) for r in rules]
    }"""
new_api_keys = """@app.get("/api/keys")
async def get_api_keys(request: Request):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized"})
        
    supabase = database.get_supabase_client()
    keys, rules = [], []
    if supabase:
        keys_res = supabase.table("api_keys").select("*").eq("user_id", user["id"]).eq("is_active", True).execute()
        keys = keys_res.data
        rules_res = supabase.table("automation_rules").select("*").eq("user_id", user["id"]).execute()
        rules = rules_res.data
    
    return {
        "success": True, 
        "keys": keys,
        "rules": rules
    }"""
content = content.replace(old_api_keys, new_api_keys)

old_gen_key = """@app.post("/api/keys/generate")
async def generate_api_key(request: Request):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized"})
        
    import secrets
    new_key = "udip_" + secrets.token_urlsafe(32)
    
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO api_keys (user_id, api_key) VALUES (?, ?)",
        (user["id"], new_key)
    )
    conn.commit()
    conn.close()
    
    return {"success": True, "api_key": new_key}"""
new_gen_key = """@app.post("/api/keys/generate")
async def generate_api_key(request: Request):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized"})
        
    import secrets
    new_key = "udip_" + secrets.token_urlsafe(32)
    
    supabase = database.get_supabase_client()
    if supabase:
        supabase.table("api_keys").insert({"user_id": user["id"], "api_key": new_key}).execute()
    
    return {"success": True, "api_key": new_key}"""
content = content.replace(old_gen_key, new_gen_key)

old_revoke_key = """@app.delete("/api/keys/{key_id}")
async def revoke_api_key(request: Request, key_id: int):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized"})
        
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE api_keys SET is_active = 0 WHERE id = ? AND user_id = ?",
        (key_id, user["id"])
    )
    conn.commit()
    conn.close()
    
    return {"success": True}"""
new_revoke_key = """@app.delete("/api/keys/{key_id}")
async def revoke_api_key(request: Request, key_id: int):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized"})
        
    supabase = database.get_supabase_client()
    if supabase:
        supabase.table("api_keys").update({"is_active": False}).eq("id", key_id).eq("user_id", user["id"]).execute()
    
    return {"success": True}"""
content = content.replace(old_revoke_key, new_revoke_key)

old_create_rule = """@app.post("/api/rules")
async def create_rule(request: Request, data: dict):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized"})
        
    import uuid
    rule_id = str(uuid.uuid4())
    
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO automation_rules (rule_id, user_id, rule_name, trigger_type, webhook_url) VALUES (?, ?, ?, ?, ?)",
        (rule_id, user["id"], data.get("rule_name"), data.get("trigger_type"), data.get("webhook_url"))
    )
    conn.commit()
    conn.close()
    
    return {"success": True, "rule_id": rule_id}"""
new_create_rule = """@app.post("/api/rules")
async def create_rule(request: Request, data: dict):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized"})
        
    import uuid
    rule_id = str(uuid.uuid4())
    
    supabase = database.get_supabase_client()
    if supabase:
        supabase.table("automation_rules").insert({
            "rule_id": rule_id, 
            "user_id": user["id"], 
            "rule_name": data.get("rule_name"), 
            "trigger_type": data.get("trigger_type"), 
            "webhook_url": data.get("webhook_url")
        }).execute()
    
    return {"success": True, "rule_id": rule_id}"""
content = content.replace(old_create_rule, new_create_rule)

old_delete_rule = """@app.delete("/api/rules/{rule_id}")
async def delete_rule(request: Request, rule_id: str):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized"})
        
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM automation_rules WHERE rule_id = ? AND user_id = ?",
        (rule_id, user["id"])
    )
    conn.commit()
    conn.close()
    
    return {"success": True}"""
new_delete_rule = """@app.delete("/api/rules/{rule_id}")
async def delete_rule(request: Request, rule_id: str):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized"})
        
    supabase = database.get_supabase_client()
    if supabase:
        supabase.table("automation_rules").delete().eq("rule_id", rule_id).eq("user_id", user["id"]).execute()
    
    return {"success": True}"""
content = content.replace(old_delete_rule, new_delete_rule)

with open("main.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Migration script executed.")
