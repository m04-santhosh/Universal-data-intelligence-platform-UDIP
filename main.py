import json
import traceback
from io import BytesIO
from fastapi import FastAPI, UploadFile, File, Request, HTTPException, Form, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, RedirectResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
import pandas as pd
import re
import sqlite3
from datetime import datetime
import difflib
import os
import logging
import time
from pydantic import BaseModel

import requests
import threading
from fastapi.security import APIKeyHeader

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
import io

import database
import auth

app = FastAPI(title="Universal Data Intelligence Platform")

IN_MEMORY_DOWNLOADS = {}

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def get_api_user(api_key: str = Depends(api_key_header)):
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    user = auth.verify_api_key(api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return user

def generate_pdf_report(user_name, project_name, data_len, trust_report, mappings_applied, recommendations):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    title_style.alignment = 1 # Center
    
    # UDIP Logo / Header
    elements.append(Paragraph("<b>UDIP - Universal Data Intelligence Platform</b>", title_style))
    elements.append(Spacer(1, 12))
    
    elements.append(Paragraph("<b>Processing Report</b>", styles['Heading2']))
    elements.append(Spacer(1, 12))
    
    # Summary
    summary_data = [
        ["Project Name:", project_name],
        ["Processing Date:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ["User Name:", user_name],
        ["Total Records:", str(data_len)],
        ["Quality Score:", f"{trust_report.get('quality_score', 0)}/100"]
    ]
    t = Table(summary_data, colWidths=[150, 300])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(t)
    elements.append(Spacer(1, 20))
    
    # Mapping Summary
    elements.append(Paragraph("<b>Mapping Summary</b>", styles['Heading2']))
    if mappings_applied:
        mapping_data = [["Original Column", "Mapped Column", "Match Type"]]
        for m in mappings_applied:
            mapping_data.append([m.get("original_column", ""), m.get("canonical_column", ""), m.get("match_type", "")])
        
        t_map = Table(mapping_data, colWidths=[150, 150, 150])
        t_map.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(t_map)
    else:
        elements.append(Paragraph("No mappings applied.", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Data Quality Report
    elements.append(Paragraph("<b>Data Quality Report</b>", styles['Heading2']))
    quality_data = [
        ["Missing Values:", str(trust_report.get('missing_values', 0))],
        ["Duplicates Merged:", str(trust_report.get('duplicates_merged', 0))],
        ["Conflicts Detected:", str(trust_report.get('conflicts_detected', 0))],
    ]
    t_qual = Table(quality_data, colWidths=[200, 250])
    t_qual.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4)
    ]))
    elements.append(t_qual)
    elements.append(Spacer(1, 20))
    
    # AI Recommendations
    elements.append(Paragraph("<b>AI Recommendations</b>", styles['Heading2']))
    if recommendations:
        for rec in recommendations:
            elements.append(Paragraph(f"• {rec}", styles['Normal']))
            elements.append(Spacer(1, 6))
    else:
        elements.append(Paragraph("No specific recommendations.", styles['Normal']))
        
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

def trigger_webhooks(user_id: str, trigger_type: str, payload: dict):
    def run_webhooks():
        try:
            supabase = database.get_supabase_client()
            if not supabase: return
            response = supabase.table("automation_rules").select("webhook_url").eq("user_id", user_id).eq("trigger_type", trigger_type).execute()
            rules = response.data or []
            
            for rule in rules:
                try:
                    import requests
                    requests.post(rule["webhook_url"], json=payload, timeout=5)
                except Exception as e:
                    logger.error(f"Webhook error to {rule['webhook_url']}: {e}")
        except Exception as e:
            print(f"Webhook skipped: {e}")
                
    import threading
    threading.Thread(target=run_webhooks, daemon=True).start()

templates = Jinja2Templates(directory="templates")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    user = auth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request=request, name="index.html", context={"user": user})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = auth.get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request=request, name="login.html")

@app.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    supabase = database.get_supabase_client()
    if not supabase:
        return templates.TemplateResponse(request=request, name="login.html", context={"error": "Database is not configured. Please check SUPABASE_URL and SUPABASE_ANON_KEY environment variables."})
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if response.session:
            access_token = response.session.access_token
            res = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
            res.set_cookie(key="session", value=access_token, httponly=True, max_age=auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
            return res
        else:
            return templates.TemplateResponse(request=request, name="login.html", context={"error": "Invalid email or password"})
    except Exception as e:
        return templates.TemplateResponse(request=request, name="login.html", context={"error": "Invalid email or password"})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    user = auth.get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request=request, name="register.html")

@app.post("/register")
async def register(request: Request, name: str = Form(...), email: str = Form(...), password: str = Form(...), confirm_password: str = Form(...)):
    if len(password) > 72:
         return templates.TemplateResponse(request=request, name="register.html", context={"error": "Password cannot exceed 72 characters. Please use a shorter password.", "name": name, "email": email})

    if len(password.encode('utf-8')) > 72:
         return templates.TemplateResponse(request=request, name="register.html", context={"error": "Password contains special characters that exceed the maximum allowed size (72 bytes). Please use a shorter password.", "name": name, "email": email})

    if password.strip() != confirm_password.strip():
         return templates.TemplateResponse(request=request, name="register.html", context={"error": "Passwords do not match", "name": name, "email": email})
    
    supabase = database.get_supabase_client()
    if not supabase:
        return templates.TemplateResponse(request=request, name="register.html", context={"error": "Database is not configured. Please check SUPABASE_URL and SUPABASE_KEY environment variables.", "name": name, "email": email})
    try:
        response = supabase.auth.sign_up({"email": email, "password": password, "options": {"data": {"name": name}}})
        if response.user:
            return RedirectResponse(url="/login?registered=true", status_code=status.HTTP_302_FOUND)
        else:
            return templates.TemplateResponse(request=request, name="register.html", context={"error": "Registration failed", "name": name, "email": email})
    except Exception as e:
        # Check if user already exists
        if "already registered" in str(e).lower() or "User already exists" in str(e):
             return templates.TemplateResponse(request=request, name="register.html", context={"error": "Email already registered", "name": name, "email": email})
        return templates.TemplateResponse(request=request, name="register.html", context={"error": str(e), "name": name, "email": email})

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="session")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    print("Dashboard route reached")
    try:
        session = request.cookies.get("session")
        print("Session:", session)
        
        if session is None:
            return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
            
        user = auth.get_current_user(request)
        print("Current user:", user)
        
        if user is None:
            return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

        supabase = database.get_supabase_client()

        response = (
            supabase.table("projects")
            .select("*")
            .eq("user_id", user["id"])
            .order("created_at", desc=True)
            .execute()
        )

        projects = response.data
        
        total_projects = len(projects)
        total_records = 0
        total_quality_score = 0
        highest_quality_project = {}
        lowest_quality_project = {}
        total_duplicates_merged = 0
        total_conflicts_detected = 0
        
        highest_score = -1
        lowest_score = 101

        for p in projects:
            p_name = p.get("project_name", "Unknown")
            p_records = int(p.get("total_records", 0) or 0)
            p_score = int(p.get("quality_score", 0) or 0)
            
            total_records += p_records
            total_quality_score += p_score
            
            if p_score > highest_score:
                highest_score = p_score
                highest_quality_project = {"name": p_name, "score": p_score}
                
            if p_score < lowest_score:
                lowest_score = p_score
                lowest_quality_project = {"name": p_name, "score": p_score}
                
            processing_results = p.get("processing_results", {})
            if isinstance(processing_results, str):
                import json
                try:
                    processing_results = json.loads(processing_results)
                except:
                    processing_results = {}
                    
            if processing_results:
                er_report = processing_results.get("entity_resolution_report", {})
                if isinstance(er_report, dict):
                    total_duplicates_merged += int(er_report.get("duplicates_merged", 0) or 0)
                    total_conflicts_detected += int(er_report.get("conflicts_detected", 0) or 0)
                    
        average_quality_score = round(total_quality_score / total_projects) if total_projects > 0 else 0
        
        if total_projects == 0:
            highest_quality_project = {}
            lowest_quality_project = {}
            
        dashboard_stats = {
            "total_projects": total_projects,
            "total_records": total_records,
            "average_quality_score": average_quality_score,
            "highest_quality_project": highest_quality_project,
            "lowest_quality_project": lowest_quality_project,
            "total_duplicates_merged": total_duplicates_merged,
            "total_conflicts_detected": total_conflicts_detected,
            "recent_projects": projects[:10]
        }
        
        print("DASHBOARD LOADED")
        print("TOTAL PROJECTS:", total_projects)
        print("TOTAL RECORDS:", total_records)
        print("AVERAGE QUALITY:", average_quality_score)

        try:
            return templates.TemplateResponse(
                request=request,
                name="dashboard.html",
                context={
                    "user": user,
                    "projects": projects,
                    "dashboard_stats": dashboard_stats
                }
            )
        except Exception as template_error:
            print("--- TEMPLATE RENDERING FAILED ---")
            error_traceback = traceback.format_exc()
            print(error_traceback)
            return PlainTextResponse(
                content=f"Template rendering error:\n\n{error_traceback}",
                status_code=500
            )

    except Exception as e:
        print("--- DASHBOARD ROUTE EXCEPTION ---")
        error_traceback = traceback.format_exc()
        print(error_traceback)
        return PlainTextResponse(
            content=f"Dashboard route error:\n\n{error_traceback}",
            status_code=500
        )

@app.delete("/api/projects/{project_id}")
async def delete_project(request: Request, project_id: str):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized"})
        
    supabase = database.get_supabase_client()
    if not supabase:
        return JSONResponse(status_code=500, content={"success": False, "error": "Database not configured"})
        
    response = supabase.table("projects").delete().eq("id", project_id).eq("user_id", user["id"]).execute()
    
    if response.data:
        return {"success": True}
    else:
        return JSONResponse(status_code=404, content={"success": False, "error": "Project not found"})

@app.get("/project/{project_id}", response_class=HTMLResponse)
async def open_project(request: Request, project_id: str):
    user = auth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        
    supabase = database.get_supabase_client()
    if not supabase:
        raise HTTPException(status_code=500, detail="Database not configured")
        
    response = supabase.table("projects").select("*").eq("id", project_id).eq("user_id", user["id"]).execute()
    
    if not response.data or not response.data[0].get("processing_results"):
        raise HTTPException(status_code=404, detail="Project not found")
        
    project_record = response.data[0]
    project_name = project_record.get("project_name", "Untitled Project")
    project_data = project_record.get("processing_results", {})
    
    if isinstance(project_data, str):
        import json
        try:
            project_data = json.loads(project_data)
        except Exception:
            project_data = {}
            
    return templates.TemplateResponse(request=request, name="project.html", context={
        "user": user,
        "project_name": project_name,
        "project_id": project_id,
        "processing_results": project_data
    })

@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    print("History route reached")
    user = auth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        
    supabase = database.get_supabase_client()
    projects = []
    if supabase:
        try:
            response = supabase.table("projects").select("*").eq("user_id", user["id"]).order("created_at", desc=True).execute()
            projects = response.data
        except Exception as e:
            print(f"Supabase Projects Query Error: {e}")
            projects = []
            
    print("History records:", projects)
    return templates.TemplateResponse(request=request, name="history.html", context={"user": user, "projects": projects})

@app.post("/api/projects/{project_id}/duplicate")
async def duplicate_project(request: Request, project_id: str):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized"})
        
    import uuid
    supabase = database.get_supabase_client()
    if not supabase:
        return JSONResponse(status_code=500, content={"success": False, "error": "Database not configured"})
    
    response = supabase.table("projects").select("*").eq("id", project_id).eq("user_id", user["id"]).execute()
    if not response.data:
        return JSONResponse(status_code=404, content={"success": False, "error": "Project not found"})
        
    project = response.data[0]
    new_id = str(uuid.uuid4())
    new_name = project["project_name"] + " (Copy)"
    
    supabase.table("projects").insert({
        "project_id": new_id,
        "user_id": user["id"],
        "project_name": new_name,
        "total_records": project.get("total_records", 0),
        "quality_score": project.get("quality_score", 0),
        "processing_results": project.get("processing_results", {})
    }).execute()
    
    return {"success": True, "new_project_id": new_id}

@app.get("/templates", response_class=HTMLResponse)
async def templates_page(request: Request):
    user = auth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        
    supabase = database.get_supabase_client()
    user_templates = []
    if supabase:
        try:
            response = supabase.table("mapping_templates").select("*").eq("user_id", user["id"]).order("created_at", desc=True).execute()
            user_templates = response.data
        except Exception:
            user_templates = []
    
    templates_with_counts = []
    for t in user_templates:
        t_dict = dict(t)
        mapping_data = t["mapping_json"] if isinstance(t["mapping_json"], dict) else json.loads(t["mapping_json"])
        t_dict["mappings_count"] = len(mapping_data.keys())
        templates_with_counts.append(t_dict)
        
    return templates.TemplateResponse(request=request, name="templates.html", context={"user": user, "mapping_templates": templates_with_counts})

@app.delete("/api/templates/{template_id}")
async def delete_template(request: Request, template_id: str):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized"})
        
    supabase = database.get_supabase_client()
    if not supabase:
        return JSONResponse(status_code=500, content={"success": False, "error": "Database not configured"})
        
    try:
        response = supabase.table("mapping_templates").delete().eq("template_id", template_id).eq("user_id", user["id"]).execute()
        
        if response.data:
            return {"success": True}
        else:
            return JSONResponse(status_code=404, content={"success": False, "error": "Template not found"})
    except Exception as e:
        return JSONResponse(status_code=404, content={"success": False, "error": f"Template missing or error: {e}"})

SCHEMA_MAPPING = {
    "customerid": "customer_id",
    "clientid": "customer_id",
    "custname": "customer_name",
    "clientname": "customer_name",
    "phone": "phone_number",
    "mobile": "phone_number",
    "contact": "phone_number",
    "phoneservice": "phone_service",
    "monthlycharge": "revenue"
}

CANONICAL_SCHEMA = [
    "customer_id",
    "customer_name",
    "phone_number",
    "phone_service",
    "revenue",
    "address",
    "email_address",
    "date_of_birth"
]

class AISchemaDiscoveryEngine:
    def __init__(self, canonical_schema, fallback_mapping):
        self.canonical_schema = canonical_schema
        self.fallback_mapping = fallback_mapping
        
        # Advanced semantic knowledge base
        self.semantic_knowledge = {
            "cust": "customer",
            "client": "customer",
            "usr": "user",
            "no": "number",
            "num": "number",
            "ref": "id",
            "identifier": "id",
            "mobile": "phone",
            "cell": "phone",
            "contact": "phone",
            "addr": "address",
            "loc": "address",
            "mail": "email",
            "dob": "date_of_birth",
            "rev": "revenue",
            "charge": "revenue",
            "amt": "amount"
        }

    def _tokenize(self, col_str):
        # Handle camelCase and snake_case
        snake_case = re.sub(r'(?<=[a-z])(?=[A-Z])', '_', str(col_str))
        snake_case = re.sub(r'[\s\W]+', '_', snake_case).lower().strip('_')
        return snake_case.split('_')

    def infer_mapping(self, original_column):
        col_str = str(original_column)
        lookup_key = re.sub(r'[\s_]+', '', col_str.lower())
        
        # 1. Fallback Dictionary Check
        if lookup_key in self.fallback_mapping:
            return self.fallback_mapping[lookup_key], 1.0, "Dictionary Match"
            
        snake_case_full = "_".join(self._tokenize(col_str))
        if snake_case_full in self.fallback_mapping.values() or lookup_key in self.fallback_mapping.values():
            return snake_case_full, 1.0, "Dictionary Match"

        # 2. AI Semantic Inference
        tokens = self._tokenize(col_str)
        expanded_tokens = [self.semantic_knowledge.get(t, t) for t in tokens]
        semantic_name = "_".join(expanded_tokens)
        
        best_match = original_column
        best_score = 0.0
        
        for canonical in self.canonical_schema:
            # Base string similarity
            score = difflib.SequenceMatcher(None, semantic_name, canonical).ratio()
            
            # Semantic overlap boost
            canonical_tokens = canonical.split('_')
            overlap = set(expanded_tokens).intersection(set(canonical_tokens))
            if overlap:
                # Boost confidence if semantic roots match
                overlap_ratio = len(overlap) / max(len(expanded_tokens), len(canonical_tokens))
                score += 0.3 * overlap_ratio
                
            if score > best_score:
                best_score = score
                best_match = canonical
                
        # Cap score for AI inference
        best_score = min(0.99, best_score)
        
        if best_score >= 0.55:
            return best_match, best_score, "AI Suggested"
            
        # Return as unmapped with low confidence
        return snake_case_full, max(0.1, best_score - 0.2), "Unmapped"

def generate_column_description(col_name):
    desc_map = {
        "customer_id": "Unique identifier for customer",
        "customer_name": "Full name of the customer",
        "phone_number": "Contact number of customer",
        "phone_service": "Indicates if the customer has phone service",
        "revenue": "Monetary value associated with customer",
        "address": "Physical location or address",
        "email_address": "Email contact information",
        "date_of_birth": "Birth date of the customer",
        "city": "City of residence",
        "ticket": "Support ticket identifier or details",
        "account_balance": "Current balance in the account"
    }
    return desc_map.get(col_name, f"Data column representing {col_name.replace('_', ' ')}")

def generate_data_catalog(df):
    catalog = []
    for col in df.columns:
        if col == "entity_id": continue
        null_pct = df[col].isnull().mean() * 100
        unique_cnt = df[col].nunique()
        samples = df[col].dropna().astype(str).head(3).tolist()
        dtype = str(df[col].dtype)
        desc = generate_column_description(col)
        catalog.append({
            "column_name": col,
            "data_type": dtype,
            "sample_values": samples,
            "null_percentage": round(null_pct, 2),
            "unique_values": unique_cnt,
            "description": desc
        })
    return catalog

def generate_insights(df, report, trust_report):
    insights = []
    insights.append(f"✓ {len(df)} unique customers identified")
    insights.append(f"✓ {report.get('duplicates_merged', 0)} duplicate records merged")
    insights.append(f"✓ Missing values detected: {trust_report.get('missing_values', 0)}")
    
    if 'revenue' in df.columns:
        insights.append("✓ Revenue column available")
        rev_series = pd.to_numeric(df['revenue'], errors='coerce').dropna()
        if not rev_series.empty:
            avg_rev = rev_series.mean()
            insights.append(f"✓ Average revenue: ₹{avg_rev:,.2f}")
            
    for col in df.columns:
        if col in ['city', 'location', 'address']:
            val_counts = df[col].value_counts()
            if not val_counts.empty:
                insights.append(f"✓ Most common {col}: {val_counts.index[0]}")
            break
            
    return insights

def generate_recommendations(df):
    recs = []
    if 'phone_number' in df.columns and df['phone_number'].nunique() > len(df) * 0.8:
        recs.append("Phone number is a strong entity key")
    if 'customer_id' in df.columns:
        recs.append("Customer ID should be primary key")
    if 'revenue' in df.columns:
        recs.append("Revenue column suitable for analytics")
    if 'city' in df.columns:
        recs.append("Consider standardizing city names")
    if not recs:
        recs.append("Data is clean and ready for analysis")
    return recs

def build_relationship_graphs(resolved_records):
    graphs = []
    for entity in resolved_records:
        name = entity.get("customer_name") or entity.get("entity_id")
        children = []
        
        for k, v in entity.items():
            if k not in ["entity_id", "customer_name", "customer_id", "phone_number"] and v is not None and str(v).strip() != "":
                display_name = str(k).replace('_', ' ').title()
                children.append({
                    "name": f"{display_name}: {v}",
                    "type": k
                })
        
        graphs.append({
            "entity_id": entity["entity_id"],
            "name": name,
            "children": children,
            "relationship_count": len(children)
        })
    return graphs

def perform_entity_resolution(records):
    customer_id_to_entity = {}
    phone_to_entity = {}
    name_to_entity = {}
    
    entities = {} # entity_id -> merged_record
    
    records_before = len(records)
    entity_counter = 1
    conflicts_detected = 0
    
    for record in records:
        customer_id = record.get('customer_id')
        phone_number = record.get('phone_number')
        customer_name = record.get('customer_name')
        
        matched_entity_id = None
        
        if customer_id and customer_id in customer_id_to_entity:
            matched_entity_id = customer_id_to_entity[customer_id]
        elif phone_number and phone_number in phone_to_entity:
            matched_entity_id = phone_to_entity[phone_number]
        elif customer_name and customer_name in name_to_entity:
            matched_entity_id = name_to_entity[customer_name]
            
        if matched_entity_id is None:
            matched_entity_id = f"ENT{entity_counter:04d}"
            entity_counter += 1
            entities[matched_entity_id] = {"entity_id": matched_entity_id}
            
        entity = entities[matched_entity_id]
        for k, v in record.items():
            if v is not None and str(v).strip() != "":
                if k not in entity or entity[k] is None or str(entity[k]).strip() == "":
                    entity[k] = v
                else:
                    if str(entity[k]).strip() != str(v).strip():
                        conflicts_detected += 1
                    
        # Update lookup maps
        if customer_id:
            customer_id_to_entity[customer_id] = matched_entity_id
        if phone_number:
            phone_to_entity[phone_number] = matched_entity_id
        if customer_name:
            name_to_entity[customer_name] = matched_entity_id
            
    resolved_records = list(entities.values())
    records_after = len(resolved_records)
    
    report = {
        "records_before_merge": records_before,
        "records_after_merge": records_after,
        "duplicates_merged": records_before - records_after,
        "conflicts_detected": conflicts_detected
    }
    
    return resolved_records, report

@app.post("/api/analyze_files")
async def analyze_files(request: Request, files: list[UploadFile] = File(...)):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized. Please log in."})
        
    try:
        if len(files) < 2:
            return JSONResponse(status_code=400, content={"success": False, "error": "Please upload at least 2 Excel files."})
            
        schema_engine = AISchemaDiscoveryEngine(CANONICAL_SCHEMA, SCHEMA_MAPPING)
        
        all_columns = set()
        
        for file in files:
            if not file.filename.endswith(('.xlsx', '.xls')):
                return JSONResponse(status_code=400, content={"success": False, "error": f"Invalid file format for {file.filename}."})
            
            contents = await file.read()
            df = pd.read_excel(BytesIO(contents))
            for col in df.columns:
                all_columns.add(str(col))
            # Rewind file pointer so it can be read again in the next request
            await file.seek(0)
            
        all_columns = list(all_columns)
        
        # AI Suggestions
        ai_suggestions = {}
        for col in all_columns:
            normalized_col, confidence, match_type = schema_engine.infer_mapping(col)
            ai_suggestions[col] = {
                "suggested": normalized_col if match_type != "Unmapped" else "ignore",
                "confidence": confidence,
                "match_type": match_type
            }
            
        # Template Matching
        supabase = database.get_supabase_client()
        templates = []
        if supabase:
            try:
                res = supabase.table("mapping_templates").select("template_id, template_name, mapping_json").eq("user_id", user["id"]).execute()
                templates = res.data
            except Exception:
                templates = []
        
        best_template = None
        best_score = 0
        
        for t in templates:
            mapping = json.loads(t["mapping_json"])
            template_keys = set(mapping.keys())
            overlap = len(template_keys.intersection(set(all_columns)))
            if len(all_columns) > 0:
                score = int((overlap / len(all_columns)) * 100)
            else:
                score = 0
                
            if score > best_score and score >= 30: # at least 30% match
                best_score = score
                best_template = {
                    "template_id": t["template_id"],
                    "template_name": t["template_name"],
                    "mapping": mapping,
                    "match_score": score
                }
                
        return {
            "success": True,
            "columns": all_columns,
            "ai_suggestions": ai_suggestions,
            "suggested_template": best_template
        }
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/api/convert")
async def convert_excel_to_json(request: Request, files: list[UploadFile] = File(...)):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized. Please log in."})
        
    try:
        if len(files) < 2:
            return JSONResponse(status_code=400, content={"success": False, "error": "Please upload at least 2 Excel files."})
        
        start_time = time.time()
        all_dataframes = []
        original_columns_report = {}
        mappings_applied_report = []
        
        schema_engine = AISchemaDiscoveryEngine(CANONICAL_SCHEMA, SCHEMA_MAPPING)

        for file in files:
            if not file.filename.endswith(('.xlsx', '.xls')):
                return JSONResponse(status_code=400, content={"success": False, "error": f"Invalid file format for {file.filename}. Please upload only Excel files."})
            
            try:
                contents = await file.read()
                if not contents:
                    return JSONResponse(status_code=400, content={"success": False, "error": f"The file {file.filename} is empty."})
                
                # Read the Excel file
                try:
                    df = pd.read_excel(BytesIO(contents))
                except Exception as ve:
                    return JSONResponse(status_code=400, content={"success": False, "error": f"The Excel file {file.filename} is corrupted. Details: {str(ve)}"})

                if df.empty:
                    return JSONResponse(status_code=400, content={"success": False, "error": f"The uploaded Excel file {file.filename} contains no data rows."})
                
                # Record original columns
                original_columns_report[file.filename] = list(df.columns)
                
                # Apply mappings
                new_columns = {}
                for col in df.columns:
                    normalized_col, confidence, match_type = schema_engine.infer_mapping(col)
                    if match_type != "Unmapped":
                        new_columns[col] = normalized_col
                        
                        existing_mapping = next((m for m in mappings_applied_report if m["original_column"] == str(col)), None)
                        if not existing_mapping:
                            mappings_applied_report.append({
                                "original_column": str(col), 
                                "canonical_column": normalized_col, 
                                "confidence_score": confidence,
                                "match_type": match_type
                            })
                
                df.rename(columns=new_columns, inplace=True)
                all_dataframes.append(df)
                
            except Exception as e:
                return JSONResponse(status_code=500, content={"success": False, "error": f"Unexpected error processing file {file.filename}: {str(e)}"})
                
        # Merge all dataframes
        if not all_dataframes:
            return JSONResponse(status_code=400, content={"success": False, "error": "No valid data found in the uploaded files."})
            
        merged_df = pd.concat(all_dataframes, ignore_index=True)
        
        import numpy as np
        import uuid
        
        # Convert all values into JSON-safe formats
        merged_df = merged_df.replace([np.inf, -np.inf], np.nan)
        merged_df = merged_df.where(pd.notnull(merged_df), None)
        
        download_id = str(uuid.uuid4())
        
        
        # Parse pandas JSON into a Python list
        json_str = merged_df.to_json(orient='records', date_format='iso', force_ascii=False)
        raw_data = json.loads(json_str)
        
        # Perform entity resolution
        data, entity_resolution_report = perform_entity_resolution(raw_data)
        
        # Build relationship graphs
        relationship_graphs = build_relationship_graphs(data)
        
        # Store in memory instead of disk
        IN_MEMORY_DOWNLOADS[download_id] = data
        
        json_bytes = json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8')
        file_size = len(json_bytes)
        if file_size == 0:
            return JSONResponse(status_code=500, content={"success": False, "error": "Generated JSON is completely empty (0 bytes)."})
            
        # 6. Log: record count, file size, download generation success
        logger.info(f"Download generation success. Record count: {len(data)}, File size: {file_size} bytes")
            
        # Get sample records safely
        sample_records = data[:10]
        
        # Calculate Data Quality Metrics
        total_fields = 0
        missing_values = 0
        for row in data:
            for k, v in row.items():
                if k != "entity_id":
                    total_fields += 1
                    if v is None or str(v).strip() == "":
                        missing_values += 1
                        
        duplicates_merged = entity_resolution_report.get("duplicates_merged", 0)
        conflicts_detected = entity_resolution_report.get("conflicts_detected", 0)
        
        # Score Logic
        missing_penalty = (missing_values / max(1, total_fields)) * 100
        conflict_penalty = min(20, conflicts_detected * 2) # minor conflicts reduce score moderately
        
        completeness_score = int(max(0, 100 - missing_penalty))
        consistency_score = int(max(0, 100 - conflict_penalty))
        duplicate_score = 100 # Duplicates merged is a positive feature
        
        final_score = int(max(0, 100 - missing_penalty - conflict_penalty))
        
        score_breakdown = {
            "completeness_score": completeness_score,
            "consistency_score": consistency_score,
            "duplicate_score": duplicate_score,
            "final_score": final_score
        }
        
        processing_time = f"{time.time() - start_time:.2f}s"
        
        project_name = f"Project - {files[0].filename}" if files else f"Upload - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        trust_report = {
            "quality_score": final_score,
            "score_breakdown": score_breakdown,
            "missing_values": missing_values,
            "duplicates_merged": duplicates_merged,
            "conflicts_detected": conflicts_detected,
            "processing_time": processing_time
        }
        
        df_resolved = pd.DataFrame(data)
        data_catalog = generate_data_catalog(df_resolved)
        data_insights = generate_insights(df_resolved, entity_resolution_report, trust_report)
        recommendations = generate_recommendations(df_resolved)
        
        result_payload = {
            "success": True,
            "original_columns": original_columns_report,
            "mappings_applied": mappings_applied_report,
            "entity_resolution_report": entity_resolution_report,
            "relationship_graphs": relationship_graphs,
            "trust_report": trust_report,
            "data_catalog": data_catalog,
            "data_insights": data_insights,
            "recommendations": recommendations,
            "download_id": download_id,
            "records_processed": len(data),
            "sample_records": sample_records
        }

        pdf_bytes = generate_pdf_report(user.get("name", "User"), project_name, len(data), trust_report, mappings_applied_report, recommendations)
        
        supabase = database.get_supabase_client()
        if supabase:
            try:
                json_path = f"{download_id}.json"
                supabase.storage.from_("exports").upload(file=json_bytes, path=json_path, file_options={"content-type": "application/json"})
                json_file_url = supabase.storage.from_("exports").get_public_url(json_path)

                pdf_path = f"{download_id}.pdf"
                supabase.storage.from_("exports").upload(file=pdf_bytes, path=pdf_path, file_options={"content-type": "application/pdf"})
                pdf_file_url = supabase.storage.from_("exports").get_public_url(pdf_path)

                supabase.table("processing_jobs").insert({
                    "id": download_id,
                    "user_id": user["id"],
                    "total_records": len(data),
                    "quality_score": final_score,
                    "json_file_url": json_file_url,
                    "pdf_file_url": pdf_file_url,
                    "status": "completed"
                }).execute()
            except Exception as e:
                logger.error(f"Supabase Storage/Jobs Error: {e}")

        result_payload["json_download"] = f"/api/download/json/{download_id}"
        result_payload["pdf_download"] = f"/api/download/pdf/{download_id}"
        result_payload["job_id"] = download_id

        if supabase:
            try:
                print("PROJECT SAVE START")
                projectData = {
                    "project_id": download_id,
                    "user_id": user["id"],
                    "project_name": project_name,
                    "total_records": len(data),
                    "quality_score": final_score,
                    "processing_results": result_payload,
                    "created_at": datetime.now().isoformat()
                }
                print(projectData)
                supabase.table("projects").insert(projectData).execute()
                print("PROJECT SAVE SUCCESS")
            except Exception as e:
                error = str(e)
                print("PROJECT SAVE FAILED", error)
                logger.error(f"Supabase DB Error in /api/convert: {e}")
        
        # Webhook triggers
        payload = {
            "project_id": download_id,
            "project_name": project_name,
            "quality_score": final_score,
            "records_processed": len(data)
        }
        trigger_webhooks(user["id"], "processing_complete", payload)
        
        if final_score < 70:
            trigger_webhooks(user["id"], "quality_below_threshold", payload)
            
        if duplicates_merged > 0:
            trigger_webhooks(user["id"], "duplicate_detected", payload)
        
        return result_payload
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": f"Internal API Error: {str(e)}"})

@app.post("/api/convert_with_mapping")
async def convert_excel_with_mapping(
    request: Request, 
    files: list[UploadFile] = File(...),
    mappings: str = Form(...),
    template_name: str = Form(None)
):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized. Please log in."})
        
    try:
        if len(files) < 2:
            return JSONResponse(status_code=400, content={"success": False, "error": "Please upload at least 2 Excel files."})
        
        start_time = time.time()
        all_dataframes = []
        original_columns_report = {}
        mappings_applied_report = []
        
        mapping_dict = json.loads(mappings)

        for file in files:
            if not file.filename.endswith(('.xlsx', '.xls')):
                return JSONResponse(status_code=400, content={"success": False, "error": f"Invalid file format for {file.filename}."})
            
            try:
                contents = await file.read()
                if not contents:
                    continue
                
                df = pd.read_excel(BytesIO(contents))
                if df.empty:
                    continue
                
                original_columns_report[file.filename] = list(df.columns)
                
                new_columns = {}
                for col in df.columns:
                    col_str = str(col)
                    if col_str in mapping_dict and mapping_dict[col_str] != "ignore":
                        normalized_col = mapping_dict[col_str]
                        new_columns[col] = normalized_col
                        
                        existing_mapping = next((m for m in mappings_applied_report if m["original_column"] == col_str), None)
                        if not existing_mapping:
                            mappings_applied_report.append({
                                "original_column": col_str, 
                                "canonical_column": normalized_col, 
                                "confidence_score": 100,
                                "match_type": "Manual"
                            })
                
                df.rename(columns=new_columns, inplace=True)
                all_dataframes.append(df)
                
            except Exception as e:
                return JSONResponse(status_code=500, content={"success": False, "error": str(e)})
                
        if not all_dataframes:
            return JSONResponse(status_code=400, content={"success": False, "error": "No valid data found."})
            
        merged_df = pd.concat(all_dataframes, ignore_index=True)
        
        import numpy as np
        import uuid
        
        merged_df = merged_df.replace([np.inf, -np.inf], np.nan)
        merged_df = merged_df.where(pd.notnull(merged_df), None)
        
        download_id = str(uuid.uuid4())
        
        
        json_str = merged_df.to_json(orient='records', date_format='iso', force_ascii=False)
        raw_data = json.loads(json_str)
        
        data, entity_resolution_report = perform_entity_resolution(raw_data)
        relationship_graphs = build_relationship_graphs(data)
        
        IN_MEMORY_DOWNLOADS[download_id] = data
        json_bytes = json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8')
        file_size = len(json_bytes)
        if file_size == 0:
            return JSONResponse(status_code=500, content={"success": False, "error": "Generated JSON is completely empty (0 bytes)."})
        sample_records = data[:10]
        
        total_fields = 0
        missing_values = 0
        for row in data:
            for k, v in row.items():
                if k != "entity_id":
                    total_fields += 1
                    if v is None or str(v).strip() == "":
                        missing_values += 1
                        
        duplicates_merged = entity_resolution_report.get("duplicates_merged", 0)
        conflicts_detected = entity_resolution_report.get("conflicts_detected", 0)
        
        missing_penalty = (missing_values / max(1, total_fields)) * 100
        conflict_penalty = min(20, conflicts_detected * 2)
        
        completeness_score = int(max(0, 100 - missing_penalty))
        consistency_score = int(max(0, 100 - conflict_penalty))
        duplicate_score = 100
        
        final_score = int(max(0, 100 - missing_penalty - conflict_penalty))
        
        score_breakdown = {
            "completeness_score": completeness_score,
            "consistency_score": consistency_score,
            "duplicate_score": duplicate_score,
            "final_score": final_score
        }
        
        processing_time = f"{time.time() - start_time:.2f}s"
        project_name = f"Project - {files[0].filename}" if files else f"Upload - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        trust_report = {
            "quality_score": final_score,
            "score_breakdown": score_breakdown,
            "missing_values": missing_values,
            "duplicates_merged": duplicates_merged,
            "conflicts_detected": conflicts_detected,
            "processing_time": processing_time
        }
        
        df_resolved = pd.DataFrame(data)
        data_catalog = generate_data_catalog(df_resolved)
        data_insights = generate_insights(df_resolved, entity_resolution_report, trust_report)
        recommendations = generate_recommendations(df_resolved)
        
        result_payload = {
            "success": True,
            "total_records": len(df_resolved) if 'df_resolved' in locals() else len(data),
            "processed_records": len(data),
            "output_file": None,
            "original_columns": original_columns_report,
            "mappings_applied": mappings_applied_report,
            "entity_resolution_report": entity_resolution_report,
            "relationship_graphs": relationship_graphs,
            "trust_report": trust_report,
            "data_catalog": data_catalog,
            "data_insights": data_insights,
            "recommendations": recommendations,
            "download_id": download_id,
            "records_processed": len(data),
            "sample_records": sample_records
        }

        pdf_bytes = generate_pdf_report(user.get("name", "User"), project_name, len(data), trust_report, mappings_applied_report, recommendations)
        
        supabase = database.get_supabase_client()
        if supabase:
            try:
                json_path = f"{download_id}.json"
                supabase.storage.from_("exports").upload(file=json_bytes, path=json_path, file_options={"content-type": "application/json"})
                json_file_url = supabase.storage.from_("exports").get_public_url(json_path)

                pdf_path = f"{download_id}.pdf"
                supabase.storage.from_("exports").upload(file=pdf_bytes, path=pdf_path, file_options={"content-type": "application/pdf"})
                pdf_file_url = supabase.storage.from_("exports").get_public_url(pdf_path)

                supabase.table("processing_jobs").insert({
                    "id": download_id,
                    "user_id": user["id"],
                    "total_records": len(data),
                    "quality_score": final_score,
                    "json_file_url": json_file_url,
                    "pdf_file_url": pdf_file_url,
                    "status": "completed"
                }).execute()
            except Exception as e:
                logger.error(f"Supabase Storage/Jobs Error: {e}")

        result_payload["json_download"] = f"/api/download/json/{download_id}"
        result_payload["pdf_download"] = f"/api/download/pdf/{download_id}"
        result_payload["job_id"] = download_id

        if supabase:
            try:
                if template_name:
                    try:
                        template_id = str(uuid.uuid4())
                        supabase.table("mapping_templates").insert({
                            "template_id": template_id,
                            "user_id": user["id"],
                            "template_name": template_name,
                            "mapping_json": json.loads(mappings) if isinstance(mappings, str) else mappings
                        }).execute()
                    except Exception as e:
                        logger.error(f"Failed to insert template: {e}")
                    
                print("PROJECT SAVE START")
                projectData = {
                    "project_id": download_id,
                    "user_id": user["id"],
                    "project_name": project_name,
                    "total_records": len(data),
                    "quality_score": final_score,
                    "processing_results": result_payload,
                    "created_at": datetime.now().isoformat()
                }
                print(projectData)
                supabase.table("projects").insert(projectData).execute()
                print("PROJECT SAVE SUCCESS")
            except Exception as e:
                error = str(e)
                print("PROJECT SAVE FAILED", error)
                logger.error(f"Supabase DB Error in /api/convert_with_mapping: {e}")
        
        # Webhook triggers
        payload = {
            "project_id": download_id,
            "project_name": project_name,
            "quality_score": final_score,
            "records_processed": len(data)
        }
        trigger_webhooks(user["id"], "processing_complete", payload)
        
        if final_score < 70:
            trigger_webhooks(user["id"], "quality_below_threshold", payload)
            
        if duplicates_merged > 0:
            trigger_webhooks(user["id"], "duplicate_detected", payload)
        
        return result_payload
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": f"Internal API Error: {str(e)}", "total_records": 0, "processed_records": 0, "output_file": None})

class QueryRequest(BaseModel):
    download_id: str
    query: str

class AskYourDataAIInterpreter:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        
    def parse_and_execute(self, query: str):
        q = query.lower()
        
        # 1. COUNT
        if "how many" in q and "unique" in q and "customer" in q:
            col = next((c for c in self.df.columns if 'customer' in c or 'id' in c), None)
            if col:
                count = self.df[col].nunique()
                return {"intent": "COUNT", "result_type": "scalar", "result": count, "interpretation": f"COUNT(DISTINCT {col})", "insight": f"{count} unique customers found.", "confidence": 95}
                
        if "how many customers" in q or "count customers" in q:
            if "by" not in q:
                count = len(self.df)
                return {"intent": "COUNT", "result_type": "scalar", "result": count, "interpretation": f"COUNT(*)", "insight": f"Total of {count} records found.", "confidence": 90}
                
        # 7. DUPLICATE_CHECK
        if "duplicate" in q:
            dups = self.df[self.df.duplicated(keep=False)]
            return {"intent": "DUPLICATE_CHECK", "result_type": "dataframe", "result": dups.where(pd.notnull(dups), None).to_dict(orient='records'), "interpretation": "df[df.duplicated()]", "insight": f"Found {len(dups)} duplicated rows.", "confidence": 95}
            
        # 8. MISSING_VALUE_CHECK
        if "missing" in q:
            if "phone" in q:
                col = next((c for c in self.df.columns if 'phone' in c), None)
                if col:
                    missing = self.df[self.df[col].isnull()]
                    return {"intent": "MISSING_VALUE_CHECK", "result_type": "dataframe", "result": missing.where(pd.notnull(missing), None).to_dict(orient='records'), "interpretation": f"df[df['{col}'].isnull()]", "insight": f"{len(missing)} records have missing {col}.", "confidence": 95}
            missing = self.df[self.df.isnull().any(axis=1)]
            return {"intent": "MISSING_VALUE_CHECK", "result_type": "dataframe", "result": missing.where(pd.notnull(missing), None).to_dict(orient='records'), "interpretation": "df[df.isnull().any(axis=1)]", "insight": f"{len(missing)} records contain at least one missing value.", "confidence": 90}

        # 6. GROUP_BY
        if "count" in q and "by" in q:
            group_col = q.split("by ")[-1].strip()
            matched_col = next((c for c in self.df.columns if group_col in c), None)
            if matched_col:
                res_df = self.df[matched_col].value_counts().reset_index()
                res_df.columns = [matched_col, 'count']
                return {"intent": "GROUP_BY", "result_type": "dataframe", "result": res_df.to_dict(orient='records'), "interpretation": f"df['{matched_col}'].value_counts()", "insight": f"Grouped data into {len(res_df)} unique {matched_col} categories.", "confidence": 92}

        # 3. TOP_N
        if "top" in q and "by" in q:
            match = re.search(r'top (\d+)', q)
            n = int(match.group(1)) if match else 5
            sort_col = q.split("by ")[-1].strip()
            matched_col = next((c for c in self.df.columns if sort_col in c), None)
            if matched_col:
                self.df[matched_col] = pd.to_numeric(self.df[matched_col], errors='coerce')
                res_df = self.df.nlargest(n, matched_col)
                return {"intent": "TOP_N", "result_type": "dataframe", "result": res_df.where(pd.notnull(res_df), None).to_dict(orient='records'), "interpretation": f"df.nlargest({n}, '{matched_col}')", "insight": f"Top {n} records based on {matched_col}.", "confidence": 94}

        # 4. AVERAGE
        if "average" in q or "mean" in q:
            words = q.split()
            matched_col = next((c for c in self.df.columns if any(w in c for w in words if len(w) > 3 and w not in ['average', 'mean', 'what', 'the', 'is'])), None)
            if matched_col:
                val = pd.to_numeric(self.df[matched_col], errors='coerce').mean()
                return {"intent": "AVERAGE", "result_type": "scalar", "result": round(val, 2), "interpretation": f"df['{matched_col}'].mean()", "insight": f"Average {matched_col} is {round(val, 2)}.", "confidence": 90}

        # 5. SUM
        if "total" in q or "sum" in q:
            words = q.split()
            matched_col = next((c for c in self.df.columns if any(w in c for w in words if len(w) > 3 and w not in ['total', 'sum', 'what', 'the', 'is'])), None)
            if matched_col:
                val = pd.to_numeric(self.df[matched_col], errors='coerce').sum()
                return {"intent": "SUM", "result_type": "scalar", "result": round(val, 2), "interpretation": f"df['{matched_col}'].sum()", "insight": f"Total {matched_col} is {round(val, 2)}.", "confidence": 90}

        # 2. FILTER (Specific queries like "premium customers", "from Bangalore")
        if "premium" in q:
            if 'revenue' in self.df.columns:
                self.df['revenue'] = pd.to_numeric(self.df['revenue'], errors='coerce')
                res_df = self.df[self.df['revenue'] >= self.df['revenue'].quantile(0.75)]
                return {"intent": "FILTER", "result_type": "dataframe", "result": res_df.where(pd.notnull(res_df), None).to_dict(orient='records'), "interpretation": "df[df['revenue'] >= df['revenue'].quantile(0.75)]", "insight": f"Found {len(res_df)} premium records (Top 25% revenue).", "confidence": 88}
                
        if "from " in q:
            city = q.split("from ")[-1].strip()
            mask = pd.Series(False, index=self.df.index)
            for col in self.df.columns:
                if self.df[col].dtype == 'object':
                    mask |= self.df[col].astype(str).str.lower().str.contains(city)
            res_df = self.df[mask]
            return {"intent": "FILTER", "result_type": "dataframe", "result": res_df.where(pd.notnull(res_df), None).to_dict(orient='records'), "interpretation": f"df[df.str.contains('{city}')]", "insight": f"Found {len(res_df)} records matching '{city}'.", "confidence": 90}

        # Fallback Filter
        if ">" in q or "<" in q or "=" in q:
            parts = re.split(r'(>|<|=)', q)
            if len(parts) >= 3:
                col_name = parts[0].replace('where', '').replace('records', '').replace('show', '').strip().split()[-1]
                op = parts[1]
                val = float(parts[2].strip())
                matched_col = next((c for c in self.df.columns if c in col_name or col_name in c), None)
                if matched_col:
                    self.df[matched_col] = pd.to_numeric(self.df[matched_col], errors='coerce')
                    if op == '>': res_df = self.df[self.df[matched_col] > val]
                    elif op == '<': res_df = self.df[self.df[matched_col] < val]
                    elif op == '=': res_df = self.df[self.df[matched_col] == val]
                    return {"intent": "FILTER", "result_type": "dataframe", "result": res_df.where(pd.notnull(res_df), None).to_dict(orient='records'), "interpretation": f"df[df['{matched_col}'] {op} {val}]", "insight": f"Filtered {len(res_df)} records.", "confidence": 95}
                    
        return {"intent": "UNKNOWN", "result_type": "scalar", "result": "I'm sorry, I couldn't understand that query. Try asking 'How many unique customers exist?' or 'Show top 5 customers by revenue'.", "interpretation": "Failed to match intent.", "insight": "No insight generated.", "confidence": 0}

@app.post("/api/query")
async def execute_query(request: Request, req: QueryRequest):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized"})
        
    if req.download_id not in IN_MEMORY_DOWNLOADS:
        raise HTTPException(status_code=404, detail="Data not found in memory (it may have expired)")
        
    df = pd.DataFrame(IN_MEMORY_DOWNLOADS[req.download_id])
    interpreter = AskYourDataAIInterpreter(df)
    
    try:
        response = interpreter.parse_and_execute(req.query)
        
        answer_text = response.get("insight", "")
        if not answer_text and response.get("result"):
            answer_text = str(response.get("result"))
            
        return {
            "success": True, 
            "answer": answer_text
        }
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "answer": "AI service unavailable"})

@app.get("/api/explore/{download_id}")
async def explore_records(request: Request, download_id: str, page: int = 1, limit: int = 100, sort_by: str = None, order: str = "asc", search: str = None):
    user = auth.get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    if download_id not in IN_MEMORY_DOWNLOADS:
        raise HTTPException(status_code=404, detail="Data not found in memory (it may have expired)")
        
    df = pd.DataFrame(IN_MEMORY_DOWNLOADS[download_id])
    
    if search:
        search = search.lower()
        mask = pd.Series(False, index=df.index)
        for col in df.columns:
            mask |= df[col].astype(str).str.lower().str.contains(search)
        df = df[mask]
        
    if sort_by and sort_by in df.columns:
        df = df.sort_values(by=sort_by, ascending=(order == "asc"))
        
    total_records = len(df)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    df_page = df.iloc[start_idx:end_idx]
    
    df_page = df_page.where(pd.notnull(df_page), None)
    return {
        "success": True,
        "total": total_records,
        "page": page,
        "limit": limit,
        "records": df_page.to_dict(orient='records'),
        "columns": list(df.columns)
    }

@app.get("/api/download/{download_id}")
async def download_file(request: Request, download_id: str, format: str = "json"):
    user = auth.get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    if download_id not in IN_MEMORY_DOWNLOADS:
        raise HTTPException(status_code=404, detail="File not found in memory")
        
    data = IN_MEMORY_DOWNLOADS[download_id]
        
    if format == "json":
        json_bytes = BytesIO(json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8'))
        return StreamingResponse(
            json_bytes,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=normalized_data.json"}
        )
    else:
        df = pd.DataFrame(data)
        output = BytesIO()
        if format == "csv":
            df.to_csv(output, index=False)
            output.seek(0)
            return StreamingResponse(
                output,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=normalized_data.csv"}
            )
        elif format == "excel":
            try:
                import openpyxl
            except ImportError:
                import subprocess
                subprocess.check_call(["pip", "install", "openpyxl"])
            df.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            return StreamingResponse(
                output,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=normalized_data.xlsx"}
            )

@app.get("/api/download/json/{job_id}")
async def download_json(request: Request, job_id: str):
    print("JSON DOWNLOAD REQUEST", job_id)
    try:
        user = auth.get_current_user(request)
        if not user:
            return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized"})
            
        supabase = database.get_supabase_client()
        if not supabase:
            return JSONResponse(status_code=500, content={"success": False, "error": "Database not configured"})
            
        try:
            res = supabase.table("projects").select("processing_results, project_name").eq("id", job_id).single().execute()
            
            processing_results = None
            project_name = "data_export"
            
            if hasattr(res, 'data') and isinstance(res.data, dict):
                processing_results = res.data.get("processing_results")
                project_name = res.data.get("project_name", project_name)
            elif hasattr(res, 'data') and isinstance(res.data, list) and len(res.data) > 0:
                processing_results = res.data[0].get("processing_results")
                project_name = res.data[0].get("project_name", project_name)
            elif isinstance(res, dict):
                data_dict = res.get("data", {}) if "data" in res else res
                processing_results = data_dict.get("processing_results")
                project_name = data_dict.get("project_name", project_name)
                
        except Exception as e:
            print("ERROR:", str(e))
            return JSONResponse(status_code=404, content={"success": False, "error": "Job not found"})

        if processing_results:
            print("JSON FILE GENERATED")
            print("JSON DOWNLOAD SUCCESS")
            from fastapi.responses import Response
            import json
            return Response(
                content=json.dumps(processing_results, indent=4),
                media_type="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="{project_name}.json"'
                }
            )
        else:
            return JSONResponse(status_code=404, content={"success": False, "error": "Processing results not found"})
            
    except Exception as e:
        print("ERROR:", str(e))
        return JSONResponse(status_code=500, content={"success": False, "error": "Database error"})

@app.get("/api/download/pdf/{job_id}")
async def download_pdf(request: Request, job_id: str):
    print("PDF REQUEST:", job_id)
    try:
        user = auth.get_current_user(request)
        if not user:
            return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized"})
            
        supabase = database.get_supabase_client()
        if not supabase:
            return JSONResponse(status_code=500, content={"success": False, "error": "Database not configured"})
            
        try:
            project = supabase.table("projects").select("*").eq("id", job_id).eq("user_id", user["id"]).single().execute()
        except Exception as e:
            print("ERROR:", str(e))
            return JSONResponse(status_code=404, content={"success": False, "error": "Project not found or query failed"})

        if not project.data:
            return JSONResponse(status_code=404, content={"success": False, "error": "Project not found"})
            
        print("PROJECT FOUND")
        
        project_data = project.data
        processing_results = project_data.get("processing_results", {})
        
        if isinstance(processing_results, str):
            import json
            try:
                processing_results = json.loads(processing_results)
            except Exception:
                processing_results = {}
                
        if not processing_results:
            return JSONResponse(status_code=404, content={"success": False, "error": "Processing results not found"})

        print("PROCESSING RESULTS FOUND")
        
        project_name = project_data.get("project_name", "Project_Report")
        total_records = project_data.get("total_records", 0)
        quality_score = project_data.get("quality_score", 0)
        
        from io import BytesIO
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        from fastapi.responses import StreamingResponse
        from datetime import datetime

        def esc(text):
            return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        title_style = styles['Heading1']
        title_style.alignment = 1 # Center
        h1 = styles['Heading1']
        h2 = styles['Heading2']
        normal = styles['Normal']
        
        # Data extraction
        records_processed = processing_results.get("records_processed", processing_results.get("processed_records", total_records))
        trust_report = processing_results.get("trust_report", {})
        breakdown = trust_report.get("score_breakdown", {})
        er_report = processing_results.get("entity_resolution_report", {})
        
        duplicates_merged = er_report.get("duplicates_merged", trust_report.get("duplicates_merged", 0))
        conflicts_detected = er_report.get("conflicts_detected", trust_report.get("conflicts_detected", 0))
        processing_time = trust_report.get("processing_time", "N/A")
        records_after_merge = int(records_processed) - int(duplicates_merged)
        
        # A. Cover Page
        story.append(Spacer(1, 100))
        story.append(Paragraph("<b>UNIVERSAL DATA INTELLIGENCE PLATFORM</b>", title_style))
        story.append(Spacer(1, 20))
        story.append(Paragraph(f"<b>Project Name:</b> {esc(project_name)}", title_style))
        story.append(Spacer(1, 40))
        story.append(Paragraph(f"<b>Generated Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal))
        story.append(Paragraph(f"<b>Records Processed:</b> {esc(records_processed)}", normal))
        story.append(Paragraph(f"<b>Quality Score:</b> {esc(quality_score)}/100", normal))
        story.append(PageBreak())
        
        title_style.alignment = 0 # Reset to left
        
        # B. Executive Summary
        story.append(Paragraph("Executive Summary", h1))
        story.append(Spacer(1, 12))
        exec_data = [
            ["Total Records", esc(total_records)],
            ["Records After Merge", esc(records_after_merge)],
            ["Duplicates Merged", esc(duplicates_merged)],
            ["Conflicts Detected", esc(conflicts_detected)],
            ["Processing Time", esc(processing_time)]
        ]
        t_exec = Table(exec_data, colWidths=[200, 200])
        t_exec.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('PADDING', (0,0), (-1,-1), 6)
        ]))
        story.append(t_exec)
        story.append(Spacer(1, 24))
        
        # C. Trust Report
        story.append(Paragraph("Trust Report", h1))
        story.append(Spacer(1, 12))
        final_score = breakdown.get("final_score", trust_report.get("quality_score", quality_score))
        completeness = breakdown.get("completeness_score", "N/A")
        consistency = breakdown.get("consistency_score", "N/A")
        duplicate = breakdown.get("duplicate_score", "N/A")
        trust_data = [
            ["Final Score", esc(final_score)],
            ["Completeness Score", esc(completeness)],
            ["Consistency Score", esc(consistency)],
            ["Duplicate Score", esc(duplicate)]
        ]
        t_trust = Table(trust_data, colWidths=[200, 200])
        t_trust.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('PADDING', (0,0), (-1,-1), 6)
        ]))
        story.append(t_trust)
        story.append(Spacer(1, 24))
        
        # D. Schema Intelligence
        story.append(Paragraph("Schema Intelligence", h1))
        story.append(Spacer(1, 12))
        mappings = processing_results.get("mappings_applied", [])
        map_data = [["Original Column", "Canonical Column", "Confidence Score", "Match Type"]]
        if isinstance(mappings, list):
            for m in mappings:
                if isinstance(m, dict):
                    orig = m.get("original_column", m.get("source", ""))
                    canon = m.get("canonical_column", m.get("target", ""))
                    conf = m.get("confidence_score", m.get("confidence", ""))
                    match = m.get("match_type", "")
                    map_data.append([esc(orig), esc(canon), esc(conf), esc(match)])
        if len(map_data) > 1:
            t_map = Table(map_data, colWidths=[150, 150, 100, 100])
            t_map.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.grey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('PADDING', (0,0), (-1,-1), 6)
            ]))
            story.append(t_map)
        else:
            story.append(Paragraph("No mappings applied.", normal))
        story.append(Spacer(1, 24))
        
        # E. Data Catalog
        story.append(Paragraph("Data Catalog", h1))
        story.append(Spacer(1, 12))
        catalog_data = [["Column Name", "Data Type", "Null %", "Description"]]
        catalog = processing_results.get("data_catalog", [])
        if isinstance(catalog, list):
            for item in catalog:
                if isinstance(item, dict):
                    col_name = item.get("column_name", item.get("field", item.get("name", "")))
                    d_type = item.get("data_type", item.get("type", ""))
                    null_pct = item.get("null_percentage", item.get("missing_percentage", "0%"))
                    desc = item.get("description", "")
                    desc = str(desc)[:80] + ("..." if len(str(desc)) > 80 else "")
                    catalog_data.append([esc(col_name), esc(d_type), esc(null_pct), esc(desc)])
                elif isinstance(item, str):
                    catalog_data.append([esc(item), "", "", ""])
                    
        if len(catalog_data) > 1:
            t_cat = Table(catalog_data, colWidths=[130, 80, 60, 230])
            t_cat.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.grey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('PADDING', (0,0), (-1,-1), 6)
            ]))
            story.append(t_cat)
        else:
            story.append(Paragraph("No data catalog available.", normal))
        story.append(Spacer(1, 24))
        
        # F. Insights
        story.append(Paragraph("Insights", h1))
        story.append(Spacer(1, 12))
        insights = processing_results.get("data_insights", processing_results.get("insights", []))
        if isinstance(insights, list) and insights:
            for ins in insights:
                val = str(ins.get("insight", ins) if isinstance(ins, dict) else ins)
                story.append(Paragraph(f"• {esc(val)}", normal))
                story.append(Spacer(1, 4))
        else:
            story.append(Paragraph("No insights available.", normal))
        story.append(Spacer(1, 24))
        
        # G. Recommendations
        story.append(Paragraph("Recommendations", h1))
        story.append(Spacer(1, 12))
        recs = processing_results.get("recommendations", [])
        if isinstance(recs, list) and recs:
            for rec in recs:
                val = str(rec.get("recommendation", rec) if isinstance(rec, dict) else rec)
                story.append(Paragraph(f"• {esc(val)}", normal))
                story.append(Spacer(1, 4))
        else:
            story.append(Paragraph("No recommendations available.", normal))
            
        doc.build(story)
        pdf_buffer.seek(0)
        
        print("PDF GENERATED")
        print("PDF DOWNLOAD SUCCESS")
        
        safe_filename = "".join([c for c in project_name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
        if not safe_filename:
            safe_filename = "report"
            
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}_report.pdf"'
            }
        )
            
    except Exception as e:
        print("ERROR:", str(e))
        return JSONResponse(status_code=500, content={"success": False, "error": f"PDF generation error: {str(e)}"})

@app.post("/api/generate_pdf_from_payload")
async def generate_pdf_from_payload(request: Request):
    try:
        payload = await request.json()
        processing_results = payload.get("processing_results", {})
        project_name = payload.get("project_name", "Project_Report")
        
        total_records = processing_results.get("total_records", processing_results.get("insights", {}).get("total_records", 0))
        quality_score = processing_results.get("trust_report", {}).get("quality_score", 0)
        
        from io import BytesIO
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        from fastapi.responses import StreamingResponse
        from datetime import datetime

        def esc(text):
            return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        title_style = styles['Heading1']
        title_style.alignment = 1 # Center
        h1 = styles['Heading1']
        h2 = styles['Heading2']
        normal = styles['Normal']
        
        # Data extraction
        records_processed = processing_results.get("records_processed", processing_results.get("processed_records", total_records))
        trust_report = processing_results.get("trust_report", {})
        breakdown = trust_report.get("score_breakdown", {})
        er_report = processing_results.get("entity_resolution_report", {})
        
        duplicates_merged = er_report.get("duplicates_merged", trust_report.get("duplicates_merged", 0))
        conflicts_detected = er_report.get("conflicts_detected", trust_report.get("conflicts_detected", 0))
        processing_time = trust_report.get("processing_time", "N/A")
        records_after_merge = int(records_processed) - int(duplicates_merged)
        
        # A. Cover Page
        story.append(Spacer(1, 100))
        story.append(Paragraph("<b>UNIVERSAL DATA INTELLIGENCE PLATFORM</b>", title_style))
        story.append(Spacer(1, 20))
        story.append(Paragraph(f"<b>Project Name:</b> {esc(project_name)}", title_style))
        story.append(Spacer(1, 40))
        story.append(Paragraph(f"<b>Generated Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal))
        story.append(Paragraph(f"<b>Records Processed:</b> {esc(records_processed)}", normal))
        story.append(Paragraph(f"<b>Quality Score:</b> {esc(quality_score)}/100", normal))
        story.append(PageBreak())
        
        title_style.alignment = 0 # Reset to left
        
        # B. Executive Summary
        story.append(Paragraph("Executive Summary", h1))
        story.append(Spacer(1, 12))
        exec_data = [
            ["Total Records", esc(total_records)],
            ["Records After Merge", esc(records_after_merge)],
            ["Duplicates Merged", esc(duplicates_merged)],
            ["Conflicts Detected", esc(conflicts_detected)],
            ["Processing Time", esc(processing_time)]
        ]
        t_exec = Table(exec_data, colWidths=[200, 200])
        t_exec.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('PADDING', (0,0), (-1,-1), 6)
        ]))
        story.append(t_exec)
        story.append(Spacer(1, 24))
        
        # C. Trust Report
        story.append(Paragraph("Trust Report", h1))
        story.append(Spacer(1, 12))
        final_score = breakdown.get("final_score", trust_report.get("quality_score", quality_score))
        completeness = breakdown.get("completeness_score", "N/A")
        consistency = breakdown.get("consistency_score", "N/A")
        duplicate = breakdown.get("duplicate_score", "N/A")
        trust_data = [
            ["Final Score", esc(final_score)],
            ["Completeness Score", esc(completeness)],
            ["Consistency Score", esc(consistency)],
            ["Duplicate Score", esc(duplicate)]
        ]
        t_trust = Table(trust_data, colWidths=[200, 200])
        t_trust.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('PADDING', (0,0), (-1,-1), 6)
        ]))
        story.append(t_trust)
        story.append(Spacer(1, 24))
        
        # D. Schema Intelligence
        story.append(Paragraph("Schema Intelligence", h1))
        story.append(Spacer(1, 12))
        mappings = processing_results.get("mappings_applied", [])
        map_data = [["Original Column", "Canonical Column", "Confidence Score", "Match Type"]]
        if isinstance(mappings, list):
            for m in mappings:
                if isinstance(m, dict):
                    orig = m.get("original_column", m.get("source", ""))
                    canon = m.get("canonical_column", m.get("target", ""))
                    conf = m.get("confidence_score", m.get("confidence", ""))
                    match = m.get("match_type", "")
                    map_data.append([esc(orig), esc(canon), esc(conf), esc(match)])
        if len(map_data) > 1:
            t_map = Table(map_data, colWidths=[150, 150, 100, 100])
            t_map.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.grey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('PADDING', (0,0), (-1,-1), 6)
            ]))
            story.append(t_map)
        else:
            story.append(Paragraph("No mappings applied.", normal))
        story.append(Spacer(1, 24))
        
        # E. Data Catalog
        story.append(Paragraph("Data Catalog", h1))
        story.append(Spacer(1, 12))
        catalog_data = [["Column Name", "Data Type", "Null %", "Description"]]
        catalog = processing_results.get("data_catalog", [])
        if isinstance(catalog, list):
            for item in catalog:
                if isinstance(item, dict):
                    col_name = item.get("column_name", item.get("field", item.get("name", "")))
                    d_type = item.get("data_type", item.get("type", ""))
                    null_pct = item.get("null_percentage", item.get("missing_percentage", "0%"))
                    desc = item.get("description", "")
                    desc = str(desc)[:80] + ("..." if len(str(desc)) > 80 else "")
                    catalog_data.append([esc(col_name), esc(d_type), esc(null_pct), esc(desc)])
                elif isinstance(item, str):
                    catalog_data.append([esc(item), "", "", ""])
                    
        if len(catalog_data) > 1:
            t_cat = Table(catalog_data, colWidths=[130, 80, 60, 230])
            t_cat.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.grey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('PADDING', (0,0), (-1,-1), 6)
            ]))
            story.append(t_cat)
        else:
            story.append(Paragraph("No data catalog available.", normal))
        story.append(Spacer(1, 24))
        
        # F. Insights
        story.append(Paragraph("Insights", h1))
        story.append(Spacer(1, 12))
        insights = processing_results.get("data_insights", processing_results.get("insights", []))
        if isinstance(insights, list) and insights:
            for ins in insights:
                val = str(ins.get("insight", ins) if isinstance(ins, dict) else ins)
                story.append(Paragraph(f"• {esc(val)}", normal))
                story.append(Spacer(1, 4))
        else:
            story.append(Paragraph("No insights available.", normal))
        story.append(Spacer(1, 24))
        
        # G. Recommendations
        story.append(Paragraph("Recommendations", h1))
        story.append(Spacer(1, 12))
        recs = processing_results.get("recommendations", [])
        if isinstance(recs, list) and recs:
            for rec in recs:
                val = str(rec.get("recommendation", rec) if isinstance(rec, dict) else rec)
                story.append(Paragraph(f"• {esc(val)}", normal))
                story.append(Spacer(1, 4))
        else:
            story.append(Paragraph("No recommendations available.", normal))
            
        doc.build(story)
        pdf_buffer.seek(0)
        
        safe_filename = "".join([c for c in project_name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
        if not safe_filename:
            safe_filename = "report"
            
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}_report.pdf"'
            }
        )
            
    except Exception as e:
        print("ERROR IN PDF GENERATION:", str(e))
        return JSONResponse(status_code=500, content={"success": False, "error": f"PDF generation error: {str(e)}"})

# ==============================================================================
# REST API (Protected by API Key)
# ==============================================================================

@app.post("/api/v1/upload")
async def api_v1_upload(files: list[UploadFile] = File(...), user: dict = Depends(get_api_user)):
    try:
        if len(files) < 3:
            return JSONResponse(status_code=400, content={"success": False, "error": "Please upload at least 3 Excel files."})
            
        schema_engine = AISchemaDiscoveryEngine(CANONICAL_SCHEMA, SCHEMA_MAPPING)
        all_columns = set()
        for file in files:
            if not file.filename.endswith(('.xlsx', '.xls')):
                return JSONResponse(status_code=400, content={"success": False, "error": f"Invalid file format for {file.filename}."})
            contents = await file.read()
            df = pd.read_excel(BytesIO(contents))
            for col in df.columns:
                all_columns.add(str(col))
            
        all_columns = list(all_columns)
        ai_suggestions = {}
        for col in all_columns:
            normalized_col, confidence, match_type = schema_engine.infer_mapping(col)
            ai_suggestions[col] = {
                "suggested": normalized_col if match_type != "Unmapped" else "ignore",
                "confidence": confidence,
                "match_type": match_type
            }
            
        supabase = database.get_supabase_client()
        templates = []
        if supabase:
            try:
                res = supabase.table("mapping_templates").select("template_id, template_name, mapping_json").eq("user_id", user["id"]).execute()
                templates = res.data
            except Exception:
                templates = []
        
        best_template = None
        best_score = 0
        for t in templates:
            mapping = json.loads(t["mapping_json"])
            template_keys = set(mapping.keys())
            overlap = len(template_keys.intersection(set(all_columns)))
            score = int((overlap / len(all_columns)) * 100) if len(all_columns) > 0 else 0
            if score > best_score and score >= 30:
                best_score = score
                best_template = {
                    "template_id": t["template_id"],
                    "template_name": t["template_name"],
                    "mapping": mapping,
                    "match_score": score
                }
                
        return {
            "success": True,
            "columns": all_columns,
            "ai_suggestions": ai_suggestions,
            "suggested_template": best_template
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/api/v1/process")
async def api_v1_process(files: list[UploadFile] = File(...), mappings: str = Form(...), template_name: str = Form(None), user: dict = Depends(get_api_user)):
    try:
        if len(files) < 3:
            return JSONResponse(status_code=400, content={"success": False, "error": "Please upload at least 3 Excel files."})
        
        start_time = time.time()
        all_dataframes = []
        original_columns_report = {}
        mappings_applied_report = []
        mapping_dict = json.loads(mappings)

        for file in files:
            if not file.filename.endswith(('.xlsx', '.xls')):
                return JSONResponse(status_code=400, content={"success": False, "error": f"Invalid file format for {file.filename}."})
            try:
                contents = await file.read()
                if not contents:
                    continue
                df = pd.read_excel(BytesIO(contents))
                if df.empty:
                    continue
                original_columns_report[file.filename] = list(df.columns)
                new_columns = {}
                for col in df.columns:
                    col_str = str(col)
                    if col_str in mapping_dict and mapping_dict[col_str] != "ignore":
                        normalized_col = mapping_dict[col_str]
                        new_columns[col] = normalized_col
                        existing_mapping = next((m for m in mappings_applied_report if m["original_column"] == col_str), None)
                        if not existing_mapping:
                            mappings_applied_report.append({
                                "original_column": col_str, 
                                "canonical_column": normalized_col, 
                                "confidence_score": 100,
                                "match_type": "Manual"
                            })
                df.rename(columns=new_columns, inplace=True)
                all_dataframes.append(df)
            except Exception as e:
                return JSONResponse(status_code=500, content={"success": False, "error": str(e)})
                
        if not all_dataframes:
            return JSONResponse(status_code=400, content={"success": False, "error": "No valid data found."})
            
        merged_df = pd.concat(all_dataframes, ignore_index=True)
        import numpy as np
        import uuid
        
        merged_df = merged_df.replace([np.inf, -np.inf], np.nan)
        merged_df = merged_df.where(pd.notnull(merged_df), None)
        
        download_id = str(uuid.uuid4())
        
        json_str = merged_df.to_json(orient='records', date_format='iso', force_ascii=False)
        raw_data = json.loads(json_str)
        data, entity_resolution_report = perform_entity_resolution(raw_data)
        relationship_graphs = build_relationship_graphs(data)
        
        IN_MEMORY_DOWNLOADS[download_id] = data
        json_bytes = json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8')
        file_size = len(json_bytes)
        if file_size == 0:
            return JSONResponse(status_code=500, content={"success": False, "error": "Generated JSON is completely empty (0 bytes)."})
        sample_records = data[:10]
        
        total_fields = 0
        missing_values = 0
        for row in data:
            for k, v in row.items():
                if k != "entity_id":
                    total_fields += 1
                    if v is None or str(v).strip() == "":
                        missing_values += 1
                        
        duplicates_merged = entity_resolution_report.get("duplicates_merged", 0)
        conflicts_detected = entity_resolution_report.get("conflicts_detected", 0)
        missing_penalty = (missing_values / max(1, total_fields)) * 100
        conflict_penalty = min(20, conflicts_detected * 2)
        completeness_score = int(max(0, 100 - missing_penalty))
        consistency_score = int(max(0, 100 - conflict_penalty))
        duplicate_score = 100
        final_score = int(max(0, 100 - missing_penalty - conflict_penalty))
        score_breakdown = {
            "completeness_score": completeness_score,
            "consistency_score": consistency_score,
            "duplicate_score": duplicate_score,
            "final_score": final_score
        }
        
        processing_time = f"{time.time() - start_time:.2f}s"
        project_name = f"API Upload - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        trust_report = {
            "quality_score": final_score,
            "score_breakdown": score_breakdown,
            "missing_values": missing_values,
            "duplicates_merged": duplicates_merged,
            "conflicts_detected": conflicts_detected,
            "processing_time": processing_time
        }
        
        df_resolved = pd.DataFrame(data)
        data_catalog = generate_data_catalog(df_resolved)
        data_insights = generate_insights(df_resolved, entity_resolution_report, trust_report)
        recommendations = generate_recommendations(df_resolved)
        
        result_payload = {
            "success": True,
            "original_columns": original_columns_report,
            "mappings_applied": mappings_applied_report,
            "entity_resolution_report": entity_resolution_report,
            "relationship_graphs": relationship_graphs,
            "trust_report": trust_report,
            "data_catalog": data_catalog,
            "data_insights": data_insights,
            "recommendations": recommendations,
            "download_id": download_id,
            "records_processed": len(data),
            "sample_records": sample_records
        }

        pdf_bytes = generate_pdf_report(user.get("name", "User"), project_name, len(data), trust_report, mappings_applied_report, recommendations)
        
        supabase = database.get_supabase_client()
        if supabase:
            try:
                json_path = f"{download_id}.json"
                supabase.storage.from_("exports").upload(file=json_bytes, path=json_path, file_options={"content-type": "application/json"})
                json_file_url = supabase.storage.from_("exports").get_public_url(json_path)

                pdf_path = f"{download_id}.pdf"
                supabase.storage.from_("exports").upload(file=pdf_bytes, path=pdf_path, file_options={"content-type": "application/pdf"})
                pdf_file_url = supabase.storage.from_("exports").get_public_url(pdf_path)

                supabase.table("processing_jobs").insert({
                    "id": download_id,
                    "user_id": user["id"],
                    "total_records": len(data),
                    "quality_score": final_score,
                    "json_file_url": json_file_url,
                    "pdf_file_url": pdf_file_url,
                    "status": "completed"
                }).execute()
            except Exception as e:
                logger.error(f"Supabase Storage/Jobs Error: {e}")

        result_payload["json_download"] = f"/api/download/json/{download_id}"
        result_payload["pdf_download"] = f"/api/download/pdf/{download_id}"
        result_payload["job_id"] = download_id

        if supabase:
            try:
                if template_name:
                    try:
                        template_id = str(uuid.uuid4())
                        supabase.table("mapping_templates").insert({
                            "template_id": template_id,
                            "user_id": user["id"],
                            "template_name": template_name,
                            "mapping_json": json.loads(mappings) if isinstance(mappings, str) else mappings
                        }).execute()
                    except Exception as e:
                        pass
                    
                print("PROJECT SAVE START")
                projectData = {
                    "project_id": download_id,
                    "user_id": user["id"],
                    "project_name": project_name,
                    "total_records": len(data),
                    "quality_score": final_score,
                    "processing_results": result_payload,
                    "created_at": datetime.now().isoformat()
                }
                print(projectData)
                supabase.table("projects").insert(projectData).execute()
                print("PROJECT SAVE SUCCESS")
            except Exception as e:
                error = str(e)
                print("PROJECT SAVE FAILED", error)
                logger.error(f"Supabase DB Error in /api/v1/process: {e}")
        
        # Webhook triggers
        payload = {
            "project_id": download_id,
            "project_name": project_name,
            "quality_score": final_score,
            "records_processed": len(data)
        }
        trigger_webhooks(user["id"], "processing_complete", payload)
        
        if final_score < 70:
            trigger_webhooks(user["id"], "quality_below_threshold", payload)
            
        if duplicates_merged > 0:
            trigger_webhooks(user["id"], "duplicate_detected", payload)
        
        return result_payload
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": f"Internal API Error: {str(e)}"})

@app.post("/api/v1/query")
async def api_v1_query(request: QueryRequest, user: dict = Depends(get_api_user)):
    try:
        if request.download_id not in IN_MEMORY_DOWNLOADS:
            return JSONResponse(status_code=404, content={"success": False, "error": "Data not found in memory"})
            
        data = IN_MEMORY_DOWNLOADS[request.download_id]
        df = pd.DataFrame(data)
        ai_interpreter = AskYourDataAIInterpreter(df)
        answer = ai_interpreter.process_query(request.query)
        return {"answer": answer}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.get("/api/v1/projects")
async def api_v1_projects(user: dict = Depends(get_api_user)):
    supabase = database.get_supabase_client()
    projects = []
    if supabase:
        response = supabase.table("projects").select("id, project_id, project_name, created_at, total_records, quality_score").eq("user_id", user["id"]).order("created_at", desc=True).execute()
        projects = response.data
    return {"projects": projects}

@app.get("/api/v1/project/{project_id}")
async def api_v1_project_detail(project_id: str, user: dict = Depends(get_api_user)):
    supabase = database.get_supabase_client()
    if not supabase:
        raise HTTPException(status_code=500, detail="Database not configured")
    response = supabase.table("projects").select("*").eq("id", project_id).eq("user_id", user["id"]).execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Project not found")
    
    proj_dict = response.data[0]
    if isinstance(proj_dict.get("processing_results"), str):
        proj_dict["processing_results"] = json.loads(proj_dict["processing_results"])
    return proj_dict

@app.get("/api/v1/templates")
async def api_v1_templates(user: dict = Depends(get_api_user)):
    supabase = database.get_supabase_client()
    templates = []
    if supabase:
        try:
            response = supabase.table("mapping_templates").select("template_id, template_name, created_at, mapping_json").eq("user_id", user["id"]).order("created_at", desc=True).execute()
            templates = response.data
        except Exception:
            templates = []
    
    result = []
    for td in templates:
        td["mapping"] = json.loads(td["mapping_json"]) if isinstance(td["mapping_json"], str) else td["mapping_json"]
        del td["mapping_json"]
        result.append(td)
    return {"templates": result}

@app.get("/api/v1/history")
async def api_v1_history(user: dict = Depends(get_api_user)):
    supabase = database.get_supabase_client()
    projects = []
    if supabase:
        try:
            response = supabase.table("projects").select("id, project_id, project_name, created_at, total_records, quality_score").eq("user_id", user["id"]).order("created_at", desc=True).execute()
            projects = response.data
        except Exception:
            projects = []
    return {"history": projects}

# ==============================================================================
# Developer Portal Routes
# ==============================================================================

import secrets

@app.get("/developer", response_class=HTMLResponse)
async def developer_page(request: Request):
    user = auth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        
    supabase = database.get_supabase_client()
    api_keys, automation_rules = [], []
    
    if supabase:
        keys_res = supabase.table("api_keys").select("*").eq("user_id", user["id"]).eq("is_active", True).execute()
        api_keys = keys_res.data
        rules_res = supabase.table("automation_rules").select("*").eq("user_id", user["id"]).execute()
        automation_rules = rules_res.data
    
    return templates.TemplateResponse(request=request, name="developer.html", context={
        "user": user, 
        "api_keys": api_keys, 
        "automation_rules": automation_rules
    })

class CreateWebhookRequest(BaseModel):
    rule_name: str
    trigger_type: str
    webhook_url: str

@app.post("/api/keys")
async def generate_api_key(request: Request):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized"})
        
    new_key = "udip_" + secrets.token_urlsafe(32)
    
    supabase = database.get_supabase_client()
    if supabase:
        supabase.table("api_keys").insert({"user_id": user["id"], "api_key": new_key}).execute()
    
    return {"success": True, "api_key": new_key}

@app.delete("/api/keys/{key_id}")
async def revoke_api_key(request: Request, key_id: int):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized"})
        
    supabase = database.get_supabase_client()
    if supabase:
        supabase.table("api_keys").update({"is_active": False}).eq("id", key_id).eq("user_id", user["id"]).execute()
    
    return {"success": True}

@app.post("/api/webhooks")
async def create_webhook(request: Request, payload: CreateWebhookRequest):
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
            "rule_name": payload.rule_name, 
            "trigger_type": payload.trigger_type, 
            "webhook_url": payload.webhook_url
        }).execute()
    
    return {"success": True, "rule_id": rule_id}

@app.delete("/api/webhooks/{rule_id}")
async def delete_webhook(request: Request, rule_id: str):
    user = auth.get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized"})
        
    supabase = database.get_supabase_client()
    if supabase:
        supabase.table("automation_rules").delete().eq("rule_id", rule_id).eq("user_id", user["id"]).execute()
    
    return {"success": True}
