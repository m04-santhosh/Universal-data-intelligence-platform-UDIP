import json
from io import BytesIO
from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import pandas as pd
import re

app = FastAPI(title="Universal Data Intelligence Platform")

templates = Jinja2Templates(directory="templates")

from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

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

def normalize_column_name(col):
    col_str = str(col)
    lookup_key = re.sub(r'[\s_]+', '', col_str.lower())
    
    if lookup_key in SCHEMA_MAPPING:
        return SCHEMA_MAPPING[lookup_key], 1.0
    
    snake_case = re.sub(r'(?<=[a-z])(?=[A-Z])', '_', col_str)
    snake_case = re.sub(r'[\s\W]+', '_', snake_case).lower().strip('_')
    
    if snake_case in SCHEMA_MAPPING.values() or lookup_key in SCHEMA_MAPPING.values():
        return snake_case, 1.0
        
    return snake_case, 0.8

def perform_entity_resolution(records):
    customer_id_to_entity = {}
    phone_to_entity = {}
    name_to_entity = {}
    
    entities = {} # entity_id -> merged_record
    
    records_before = len(records)
    entity_counter = 1
    
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
            if v is not None:
                if k not in entity or entity[k] is None:
                    entity[k] = v
                    
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
        "duplicates_merged": records_before - records_after
    }
    
    return resolved_records, report

@app.post("/api/convert")
async def convert_excel_to_json(files: list[UploadFile] = File(...)):
    try:
        if len(files) < 3:
            return JSONResponse(status_code=400, content={"success": False, "error": "Please upload at least 3 Excel files."})
        
        all_dataframes = []
        original_columns_report = {}
        mappings_applied_report = []

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
                    normalized_col, confidence = normalize_column_name(col)
                    if normalized_col != col:
                        new_columns[col] = normalized_col
                        mapping_entry = {
                            "original_column": str(col), 
                            "canonical_column": normalized_col, 
                            "confidence_score": confidence
                        }
                        if mapping_entry not in mappings_applied_report:
                            mappings_applied_report.append(mapping_entry)
                
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
        os.makedirs("temp_downloads", exist_ok=True)
        filepath = os.path.join("temp_downloads", f"{download_id}.json")
        
        # Parse pandas JSON into a Python list
        json_str = merged_df.to_json(orient='records', date_format='iso', force_ascii=False)
        raw_data = json.loads(json_str)
        
        # Perform entity resolution
        data, entity_resolution_report = perform_entity_resolution(raw_data)
        
        # Write pretty-printed resolved JSON to disk
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(json.dumps(data, indent=2, ensure_ascii=False))
        
        # 5. Add validation: file size > 0, valid JSON, UTF-8 encoding
        file_size = os.path.getsize(filepath)
        if file_size == 0:
            return JSONResponse(status_code=500, content={"success": False, "error": "Generated JSON file is completely empty (0 bytes)."})
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                json.load(f)
        except UnicodeDecodeError:
            return JSONResponse(status_code=500, content={"success": False, "error": "Generated file is not valid UTF-8."})
        except json.JSONDecodeError as e:
            return JSONResponse(status_code=500, content={"success": False, "error": f"Generated file is not valid JSON: {str(e)}"})
            
        # 6. Log: record count, file size, download generation success
        logger.info(f"Download generation success. Record count: {len(data)}, File size: {file_size} bytes")
            
        # Get sample records safely
        sample_records = data[:10]
        
        return {
            "success": True,
            "original_columns": original_columns_report,
            "mappings_applied": mappings_applied_report,
            "entity_resolution_report": entity_resolution_report,
            "download_id": download_id,
            "records_processed": len(data),
            "sample_records": sample_records
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": f"Internal API Error: {str(e)}"})

@app.get("/api/download/{download_id}")
async def download_file(download_id: str):
    filepath = os.path.join("temp_downloads", f"{download_id}.json")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
        
    def iterfile():
        with open(filepath, mode="rb") as file_like:
            yield from file_like

    return StreamingResponse(
        iterfile(),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=normalized_data.json"}
    )
