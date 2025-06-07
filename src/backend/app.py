from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import uvicorn
from google import genai
import requests
import os
from schemas import *
from dotenv import load_dotenv
import sentence_transformers
import numpy as np
from contextlib import asynccontextmanager
import logging
import traceback

load_dotenv()

logger = logging.getLogger(__name__)

API_KEY = os.getenv("PARTS_CATALOG_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HAYNES_PRO_USERNAME = os.getenv("HAYNES_PRO_USERNAME")
HAYNES_PRO_PASSWORD = os.getenv("HAYNES_PRO_PASSWORD")

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up...")
    global model
    model = sentence_transformers.SentenceTransformer('all-MiniLM-L6-v2')
    yield
    print("Shutting down...")
    model = None

app = FastAPI(
    title="JobNPart Backend API",
    description="API for searching parts and managing job interactions.",
    version="0.1.0",
    lifespan=lifespan
)

origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "https://jobnpart.vercel.app"
]

app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_credentials=False, 
    allow_methods=["*"], 
    allow_headers=["*"],
)

def find_best_match(job_description: str, items_list: List[dict], text_key: str = "name") -> Optional[tuple]:
    """
    Finds the best matching item from a list based on semantic similarity to the job_description.

    Args:
        job_description: The text description to match against.
        items_list: A list of dictionaries, where each dictionary represents an item.
        text_key: The key in each dictionary that contains the text to compare.

    Returns:
        A tuple (item_id, item_text, item_object) for the best match, or None if no match is found.
    """
    model = sentence_transformers.SentenceTransformer('all-MiniLM-L6-v2')
    job_description_embedding = model.encode(job_description)
    best_match_similarity = -1.0  # Cosine similarity ranges from -1 to 1
    best_match_details = None

    if not items_list:
        return None

    for item in items_list:
        item_text = item.get(text_key)
        if not item_text:
            continue

        item_embedding = model.encode(item_text)
        # Ensure embeddings are 1-D arrays for dot product
        job_desc_emb_flat = job_description_embedding.flatten()
        item_emb_flat = item_embedding.flatten()

        cosine_similarity = np.dot(job_desc_emb_flat, item_emb_flat) / \
                            (np.linalg.norm(job_desc_emb_flat) * np.linalg.norm(item_emb_flat))
        
        if cosine_similarity > best_match_similarity:
            best_match_similarity = cosine_similarity
            best_match_details = (item.get("id"), item_text, item)
            
    return best_match_details

# --- API Endpoints ---

@app.post("/analyse-job")
def analyse_job(job_data: JobData) -> List[Parts]:
    """
    Analyse a job description and return a list of parts that are needed.
    """
    car_info = requests.get(f"https://api.parts-catalogs.com/v1/car/info?q={job_data.vin}", headers={"Authorization": f"{API_KEY}"})
    if car_info.status_code == 200:
        catalog_id = car_info.json()[0]["catalogId"]
        car_id = car_info.json()[0]["carId"]
        group_id = None
    else:
        catalog_id = "skoda"
        car_id = "6f02b148166fda26b20d2e22da07b4d8"
        
    parts_list = []
    
    for work_item in job_data.workItems:
        has_parts = False
        group_id = None
        while has_parts!=True:
            if group_id is None:
                groups_url = f"https://api.parts-catalogs.com/v1/catalogs/{catalog_id}/groups2?carId={car_id}"
                groups_response = requests.get(groups_url, headers={"Authorization": f"{API_KEY}"})
                print(groups_response.json())
                best_match_group = find_best_match(work_item.description, groups_response.json())
                #print("work item: ", work_item.description)
                #print("best match group: ", best_match_group)
                group_id = best_match_group[0]
                if groups_response.json()[best_match_group[2]]["hasParts"] is True:
                    has_parts = True
                    print(groups_response.json()[best_match_group[2]]["name"] + " has parts")
            else:
                group_url = f"https://api.parts-catalogs.com/v1/catalogs/{catalog_id}/groups2?carId={car_id}&groupId={group_id}"
                group_response = requests.get(group_url, headers={"Authorization": f"{API_KEY}"})
                best_match_group = find_best_match(work_item.description, group_response.json())
                #print(best_match_group)
                group_id = best_match_group[0]
                if group_response.json()[best_match_group[2]]["hasParts"] is True:
                    has_parts = True
                    print(group_response.json()[best_match_group[2]]["name"] + " has parts")
                    
        parts_url = f"https://api.parts-catalogs.com/v1/catalogs/{catalog_id}/parts2?carId={car_id}&groupId={group_id}"
        parts_response = requests.get(parts_url, headers={"Authorization": f"{API_KEY}"})
        parts = parts_response.json()
        parts_list.append(parts)
    print(parts_list)
    return parts_list
      
@app.post("/haynes-pro")
def haynes_pro(job_data: HaynesProJobData):
    try:
        results_list = []
        response = requests.get(f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/getAuthenticationVrid?distributorUsername={HAYNES_PRO_USERNAME}&distributorPassword={HAYNES_PRO_PASSWORD}&username=jnpda2025")
        if response.json()["statusCode"] == 0:
            vrid = response.json()["vrid"]
        else:
            print(response.text)
            exit()

        # 2. Decode VIN
        vin_decode_response = requests.get(
            f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/decodeVINV4?vrid={vrid}&vin={job_data.vin}&descriptionLanguage=en"
        )
        if vin_decode_response.status_code != 200:
            print(f"Haynes Pro VIN decoding failed: {vin_decode_response.text}")
            return {"error": "Haynes Pro VIN decoding failed", "details": vin_decode_response.text}
        
        vehicle_info_list = vin_decode_response.json()
        if not vehicle_info_list or not isinstance(vehicle_info_list, list) or not vehicle_info_list[0].get("id"):
            print(f"Invalid vehicle info from VIN decode: {vehicle_info_list}")
            return {"error": "Invalid vehicle info from Haynes Pro", "details": vehicle_info_list}
        car_type_id = vehicle_info_list[0]["id"]

        # 3. Get Repair Time Types (e.g., Standard Times)
        rt_types_response = requests.get(
            f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/getRepairtimeTypesV2?vrid={vrid}&carTypeId={car_type_id}&descriptionLanguage=en"
        )
        if rt_types_response.status_code != 200:
            print(f"Failed to get repair time types: {rt_types_response.text}")
            return {"error": "Failed to get repair time types", "details": rt_types_response.text}

        repairtime_types = rt_types_response.json()
        if not repairtime_types or not isinstance(repairtime_types, list):
            print(f"No repair time types found: {repairtime_types}")
            return {"error": "No repair time types found", "details": repairtime_types}
        
        """For now we only use the first repair time type but going forward we should add a search for the best match"""
        target_repairtime_type = repairtime_types[0]
        target_repairtime_type_id = target_repairtime_type['repairtimeTypeId']
        type_category = target_repairtime_type.get('typeCategory', 'CAR')
        
        matched_work_items = []
        for work_item in job_data.workItems:
            nodeId = "root"
            has_subnodes = True
            while has_subnodes:
                main_groups_url = f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/getRepairtimeSubnodesByGroupV4?vrid={vrid}&descriptionLanguage=en&repairtimeTypeId={target_repairtime_type_id}&typeCategory={type_category}&nodeId={nodeId}"
                main_groups_resp = requests.get(main_groups_url)
                # find the best match for the work item in the main groups
                best_match_group = find_best_match(work_item.title, main_groups_resp.json(), text_key="title")
                if best_match_group:
                    nodeId = best_match_group[0]
                    has_subnodes = best_match_group[2].get("hasSubnodes", False)
                else:
                    has_subnodes = False
                    
                #print(best_match_group)
                if has_subnodes!=True:
                    matched_work_items.append({nodeId: work_item})
        
        for work_item in matched_work_items:
            nodeId = list(work_item.keys())[0]
            response = requests.get(f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/getRepairtimeInfosV4?vrid={vrid}&descriptionLanguage=en&repairtimeTypeId={target_repairtime_type_id}&typeCategory={type_category}&nodeId={nodeId}")
            repairtime_infos = response.json()
            print(repairtime_infos)
            results_list.append(repairtime_infos)
    except Exception as e:
        logger.info(e)
        logger.info(traceback.format_exec())
        return {"title":"error"}
    return results_list
    

@app.get("/")
def read_root():
    return {"message": "Welcome to the JobNPart Backend API"}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
