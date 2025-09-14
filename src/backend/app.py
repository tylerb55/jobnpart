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
from supabase import create_client, Client
from datetime import datetime
import json
import re

load_dotenv()

logger = logging.getLogger(__name__)

API_KEY = os.getenv("PARTS_CATALOG_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HAYNES_PRO_USERNAME = os.getenv("HAYNES_PRO_USERNAME")
HAYNES_PRO_PASSWORD = os.getenv("HAYNES_PRO_PASSWORD")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@asynccontextmanager
async def lifespan(_: FastAPI):
    print("Starting up...")
    global model
    model = sentence_transformers.SentenceTransformer('intfloat/e5-base-v2')
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
    #model = sentence_transformers.SentenceTransformer('intfloat/e5-base-v2')
    job_description_embedding = model.encode(job_description)
    best_match_similarity = -1.0  # Cosine similarity ranges from -1 to 1
    best_match_details = None

    if not items_list:
        return None
    
    print(f"items_list: {items_list}")

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

def chose_category(job_title: str, model_type: str) -> str:
    categories = ["ENGINE","TRANSMISSION","STEERING","BRAKES","EXTERIOR","ELECTRONICS","QUICKGUIDES"]
    if model_type == "gemini":
        gen_model = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"Given the following job description: {job_title}, choose the most appropriate category from the following list: {categories}. Only return the category, no other text."
        response = gen_model.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text
    elif model_type == "sentence_transformer":
        #model = sentence_transformers.SentenceTransformer('all-MiniLM-L6-v2')
        job_description_embedding = model.encode(job_title)
        best_match_similarity = -1.0
        best_match_details = None
        for category in categories:
            category_embedding = model.encode(category)
            cosine_similarity = np.dot(job_description_embedding, category_embedding) / \
                                (np.linalg.norm(job_description_embedding) * np.linalg.norm(category_embedding))
            if cosine_similarity > best_match_similarity:
                best_match_similarity = cosine_similarity
                best_match_details = category
        return best_match_details
    else:
        print("Invalid model: Select gemini or sentence_transformer")
        return None

def log_api_call(endpoint: str, tenant: str, vin: str, full_url: str, method: str = "GET"):
    """
    Log individual API call information to Supabase table
    
    Args:
        endpoint: The internal endpoint being called (analyse-job, haynes-pro, etc.)
        tenant: The tenant making the call
        vin: The VIN number for the call
        full_url: The full URL being called
        method: HTTP method (GET, POST, etc.)
    """
    try:
        # Extract base URL from full URL
        from urllib.parse import urlparse
        parsed_url = urlparse(full_url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        call_data = {
            "endpoint": endpoint,
            "tenant": tenant,
            "vin": vin,
            "base_url": base_url,
            "full_url": full_url,
            "method": method,
            "timestamp": datetime.utcnow().isoformat(),
            "call_count": 1
        }
        
        result = supabase.table("api_calls").insert(call_data).execute()
        logger.info(f"API call logged: {method} {full_url} for tenant {tenant}")
        
    except Exception as e:
        logger.error(f"Failed to log API call: {e}")
        # Don't raise the exception to avoid breaking the main API functionality

# --- Helpers for building full repair tree ---

def _fetch_repair_subnodes(vrid: str, repairtime_type_id: int, type_category: str, node_id: str, description_language: str = "en") -> list:
    """
    Fetch one level of subnodes for a given nodeId.
    """
    subnodes_url = (
        f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/"
        f"getRepairtimeSubnodesByGroupV4?vrid={vrid}&descriptionLanguage={description_language}"
        f"&repairtimeTypeId={repairtime_type_id}&typeCategory={type_category}&nodeId={node_id}"
    )
    response = requests.get(subnodes_url)
    try:
        return response.json()
    except Exception:
        return []


def build_full_repair_tree(vrid: str, repairtime_type_id: int, type_category: str, description_language: str = "en", root_node_id: str = "root") -> dict:
    """
    Recursively traverse all subnodes starting from root and return the entire tree structure.
    """
    visited = set()
    api_call_count = 0

    def dfs(node_id: str, parent_id: Optional[str]) -> dict:
        nonlocal api_call_count
        # Prevent accidental cycles
        if node_id in visited:
            return {"nodeId": node_id, "parent": parent_id, "groups": []}
        visited.add(node_id)

        api_call_count += 1
        groups = _fetch_repair_subnodes(vrid, repairtime_type_id, type_category, node_id, description_language)
        result_groups = []

        for group in groups:
            group_id = group.get("id")
            # Basic shape we keep from the API
            node = {
                "id": group_id,
                "description": group.get("description"),
                "hasSubnodes": group.get("hasSubnodes", False),
                "hasInfoGroups": group.get("hasInfoGroups", False),
                "value": group.get("value"),
                "parent": node_id,
                "children": []
            }

            if group.get("hasSubnodes", False) is True:
                node["children"] = dfs(group_id, node_id).get("groups", [])

            result_groups.append(node)

        return {"nodeId": node_id, "parent": parent_id, "groups": result_groups}

    root = dfs(root_node_id, None)
    root["api_call_count"] = api_call_count
    return root


def save_tree_json(tree: dict, vin: str) -> str:
    """
    Save the tree to src/backend/jsons/<vin>_repair_tree.json and return the file path.
    """
    directory = os.path.join("src", "backend", "jsons")
    os.makedirs(directory, exist_ok=True)
    filename = f"{vin}_repair_tree.json"
    path = os.path.join(directory, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=2)
    return path

# --- API Endpoints ---

@app.post("/analyse-job")
def analyse_job(job_data: JobData) -> List[Parts]:
    """
    Analyse a job description and return a list of parts that are needed.
    """
    car_info_url = f"https://api.parts-catalogs.com/v1/car/info?q={job_data.vin}"
    log_api_call("analyse-job", job_data.tenant, job_data.vin, car_info_url)
    car_info = requests.get(car_info_url, headers={"Authorization": f"{API_KEY}"})
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
                log_api_call("analyse-job", job_data.tenant, job_data.vin, groups_url)
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
                log_api_call("analyse-job", job_data.tenant, job_data.vin, group_url)
                group_response = requests.get(group_url, headers={"Authorization": f"{API_KEY}"})
                best_match_group = find_best_match(work_item.description, group_response.json())
                #print(best_match_group)
                group_id = best_match_group[0]
                if group_response.json()[best_match_group[2]]["hasParts"] is True:
                    has_parts = True
                    print(group_response.json()[best_match_group[2]]["name"] + " has parts")
                    
        parts_url = f"https://api.parts-catalogs.com/v1/catalogs/{catalog_id}/parts2?carId={car_id}&groupId={group_id}"
        log_api_call("analyse-job", job_data.tenant, job_data.vin, parts_url)
        parts_response = requests.get(parts_url, headers={"Authorization": f"{API_KEY}"})
        parts = parts_response.json()
        parts_list.append(parts)
    print(parts_list)
    return parts_list


@app.post("/haynes-pro")
def haynes_pro(job_data: HaynesProJobData):
    try:
        results_list = []
        auth_url = f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/getAuthenticationVrid?distributorUsername={HAYNES_PRO_USERNAME}&distributorPassword={HAYNES_PRO_PASSWORD}&username=jnpda2025"
        log_api_call("haynes-pro", job_data.tenant, job_data.vin, auth_url)
        response = requests.get(auth_url)
        if response.json()["statusCode"] == 0:
            vrid = response.json()["vrid"]
        else:
            print(response.text)
            exit()

        # 2. Decode VIN
        vin_decode_url = f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/decodeVINV4?vrid={vrid}&vin={job_data.vin}&descriptionLanguage=en"
        log_api_call("haynes-pro", job_data.tenant, job_data.vin, vin_decode_url)
        vin_decode_response = requests.get(vin_decode_url)
        if vin_decode_response.status_code != 200:
            print(f"Haynes Pro VIN decoding failed: {vin_decode_response.text}")
            return {"error": "Haynes Pro VIN decoding failed", "details": vin_decode_response.text}
        
        vehicle_info_list = vin_decode_response.json()
        if not vehicle_info_list or not isinstance(vehicle_info_list, list) or not vehicle_info_list[0].get("id"):
            print(f"Invalid vehicle info from VIN decode: {vehicle_info_list}")
            return {"error": "Invalid vehicle info from Haynes Pro", "details": vehicle_info_list}
        car_type_id = vehicle_info_list[0]["id"]
        print(f"car type id: {car_type_id}")

        # 3. Get Repair Time Types (e.g., Standard Times)
        rt_types_url = f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/getRepairtimeTypesV2?vrid={vrid}&carTypeId={car_type_id}&descriptionLanguage=en"
        log_api_call("haynes-pro", job_data.tenant, job_data.vin, rt_types_url)
        rt_types_response = requests.get(rt_types_url)
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
        print(f"target repair time type id: {target_repairtime_type_id}")
        type_category = target_repairtime_type.get('typeCategory', 'CAR')
        
        car_type_group = chose_category(job_data.workItems[0].title, "sentence_transformer")
        print(f"job title: {job_data.workItems[0].title}")
        print(f"car type group: {car_type_group}")
        
        matched_work_items = []
        for work_item in job_data.workItems:
            nodeId = "root"
            has_subnodes = True
            while has_subnodes:
                main_groups_url = f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/getRepairtimeSubnodesByGroupV4?vrid={vrid}&descriptionLanguage=en&repairtimeTypeId={target_repairtime_type_id}&typeCategory={type_category}&nodeId={nodeId}&carTypeGroup={car_type_group}"
                log_api_call("haynes-pro", job_data.tenant, job_data.vin, main_groups_url)
                main_groups_resp = requests.get(main_groups_url).json()
                main_groups = [group for group in main_groups_resp if group.get("hasSubnodes", False) is True or group.get("hasInfoGroups", False) is True]
                # find the best match for the work item in the main groups
                best_match_group = find_best_match(work_item.title, main_groups, text_key="description")
                if best_match_group:
                    nodeId = best_match_group[0]
                    has_subnodes = best_match_group[2].get("hasSubnodes", False)
                else:
                    has_subnodes = False
                    
                print(f"best match group: {best_match_group}")
                if has_subnodes==False:
                    print(main_groups)
                    matched_work_items.append({"nodeId": nodeId, "description": best_match_group[2].get("description"), "work_item": work_item, "main_groups": main_groups, "value": best_match_group[2].get("value")})
        
        for work_item in matched_work_items:
            #print(f"work item: {work_item}")
            nodeId = work_item.get("nodeId")
            repairtime_infos_url = f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/getRepairtimeInfosV4?vrid={vrid}&descriptionLanguage=en&repairtimeTypeId={target_repairtime_type_id}&typeCategory={type_category}&nodeId={nodeId}"
            log_api_call("haynes-pro", job_data.tenant, job_data.vin, repairtime_infos_url)
            response = requests.get(repairtime_infos_url)
            repairtime_infos = response.json()
            print(f"repairtime infos: {repairtime_infos}")
            results_list.append({"car_type_id": car_type_id, "nodeId": nodeId, "description": work_item.get("description"), "repairtime_infos": repairtime_infos, "main_groups": work_item.get("main_groups"), "value": work_item.get("value")})
    except Exception as e:
        print(e)
        print(traceback.format_exc())
        return {"title":"error"}
    return {
        "results": results_list,
        "tree_structure": tree_structure,
        "matched_work_items": matched_work_items
    }

def repair_tasks(job_data, vrid, car_type_id):
    try:
        results_list = []
        #text_search = f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/getRepairtimeSubnodesTextSearchV4?vrid={vrid}&descriptionLanguage=en&repairtimeTypeId={target_repairtime_type_id}&typeCategory={type_category}&nodeId={nodeId}&carTypeGroup={car_type_group}&searchText={job_data.workItems[0].title}"
        #log_api_call("haynes-pro", job_data.tenant, job_data.vin, text_search)
        #text_search_response = requests.get(text_search)
        #text_search_response = text_search_response.json()
        #print(f"text search response: {text_search_response}")
        #return text_search_response
    
        
        
        # 3. Get Repair Time Types (e.g., Standard Times)
        rt_types_url = f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/getRepairtimeTypesV2?vrid={vrid}&carTypeId={car_type_id}&descriptionLanguage=en"
        log_api_call("haynes-pro", job_data.tenant, job_data.vin, rt_types_url)
        rt_types_response = requests.get(rt_types_url)
        if rt_types_response.status_code != 200:
            print(f"Failed to get repair time types: {rt_types_response.text}")
            return {"error": "Failed to get repair time types", "details": rt_types_response.text}

        repairtime_types = rt_types_response.json()
        print(f"repair time types: {repairtime_types}")
        if not repairtime_types or not isinstance(repairtime_types, list):
            print(f"No repair time types found: {repairtime_types}")
            return {"error": "No repair time types found", "details": repairtime_types}
        
        """For now we only use the first repair time type but going forward we should add a search for the best match"""
        target_repairtime_type = repairtime_types[0]
        target_repairtime_type_id = target_repairtime_type['repairtimeTypeId']
        print(f"target repair time type id: {target_repairtime_type_id}")
        type_category = target_repairtime_type.get('typeCategory', 'CAR')
        
        car_type_group = chose_category(job_data.workItems[0].title, "sentence_transformer")
        print(f"job title: {job_data.workItems[0].title}")
        print(f"car type group: {car_type_group}")
        
        matched_work_items = []
        tree_structure = {}  # Dictionary to store the complete tree structure

        for work_item in job_data.workItems:
            nodeId = "root"
            has_subnodes = True
            work_item_tree = {}  # Tree structure for this specific work item
            current_path = []  # Track the path through the tree

            while has_subnodes:
                #main_groups_url = f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/getRepairtimeSubnodesByGroupV4?vrid={vrid}&descriptionLanguage=en&repairtimeTypeId={target_repairtime_type_id}&typeCategory={type_category}&nodeId={nodeId}"
                main_groups_url = f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/getRepairtimeSubnodesTextSearchV4?vrid={vrid}&descriptionLanguage=en&repairtimeTypeId={target_repairtime_type_id}&typeCategory={type_category}&nodeId={nodeId}&searchText={work_item.invoice_description}"#&carTypeGroup={car_type_group}
                log_api_call("haynes-pro", job_data.tenant, job_data.vin, main_groups_url)
                main_groups_resp = requests.get(main_groups_url).json()
                main_groups = [group for group in main_groups_resp]

                # Save this level to the global tree structure
                level_key = f"{work_item.title}_{nodeId}"
                if level_key not in tree_structure:
                    tree_structure[level_key] = {
                        "nodeId": nodeId,
                        "parent_path": current_path.copy(),
                        "groups": main_groups,
                        "work_item_title": work_item.title,
                        "level": len(current_path)
                    }

                # Also save to work item specific tree
                path_key = "_".join(current_path + [nodeId]) if current_path else nodeId
                work_item_tree[path_key] = {
                    "nodeId": nodeId,
                    "groups": main_groups,
                    "level": len(current_path)
                }

                # find the best match for the work item in the main groups
                best_match_group = find_best_match(work_item.title, main_groups, text_key="description")
                if best_match_group:
                    current_path.append(nodeId)  # Add current node to path
                    nodeId = best_match_group[0]
                    has_subnodes = best_match_group[2].get("hasSubnodes", False)
                else:
                    has_subnodes = False

                print(f"best match group: {best_match_group}")
                if has_subnodes==False:
                    print(main_groups)
                    matched_work_items.append({
                        "nodeId": nodeId,
                        "description": best_match_group[2].get("description") if best_match_group else None,
                        "work_item": work_item,
                        "main_groups": main_groups,
                        "value": best_match_group[2].get("value") if best_match_group else None,
                        "tree_path": current_path.copy(),
                        "work_item_tree": work_item_tree
                    })
        
        for work_item in matched_work_items:
            #print(f"work item: {work_item}")
            nodeId = work_item.get("nodeId")
            repairtime_infos_url = f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/getRepairtimeInfosV4?vrid={vrid}&descriptionLanguage=en&repairtimeTypeId={target_repairtime_type_id}&typeCategory={type_category}&nodeId={nodeId}"
            print(f"repairtime infos url: {repairtime_infos_url}")
            log_api_call("haynes-pro", job_data.tenant, job_data.vin, repairtime_infos_url)
            response = requests.get(repairtime_infos_url)
            repairtime_infos = response.json()
            print(f"repairtime infos: {repairtime_infos}")
            results_list.append({"car_type_id": car_type_id, "nodeId": nodeId, "description": work_item.get("description"), "repairtime_infos": repairtime_infos, "main_groups": work_item.get("main_groups"), "value": work_item.get("value")})
    except Exception as e:
        print(e)
        print(traceback.format_exc())
        return {"title":"error"}
    return {
        "results": results_list,
        "tree_structure": tree_structure,
        "matched_work_items": matched_work_items,
        "vrid": vrid,
        "type_category": type_category,
        "target_repairtime_type_id": target_repairtime_type_id
    }
    
@app.post("/create-tree")
def create_tree(job_data: CreateTreeJobData):
    try:
        # 1) Authenticate
        auth_url = f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/getAuthenticationVrid?distributorUsername={HAYNES_PRO_USERNAME}&distributorPassword={HAYNES_PRO_PASSWORD}&username=jnpda2025"
        auth_resp = requests.get(auth_url)
        auth_json = auth_resp.json()
        if auth_json.get("statusCode") != 0:
            return {"title": "error", "message": "Authentication failed", "details": auth_json}
        vrid = auth_json.get("vrid")

        # 2) Decode VIN
        vin_decode_url = f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/decodeVINV4?vrid={vrid}&vin={job_data.vin}&descriptionLanguage=en"
        vin_decode_response = requests.get(vin_decode_url)
        if vin_decode_response.status_code != 200:
            return {"title": "error", "message": "VIN decode failed", "details": vin_decode_response.text}
        vehicle_info_list = vin_decode_response.json()
        if not vehicle_info_list or not isinstance(vehicle_info_list, list) or not vehicle_info_list[0].get("id"):
            return {"title": "error", "message": "Invalid vehicle info", "details": vehicle_info_list}
        car_type_id = vehicle_info_list[0]["id"]

        # 3) Get repair time type (take first)
        rt_types_url = f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/getRepairtimeTypesV2?vrid={vrid}&carTypeId={car_type_id}&descriptionLanguage=en"
        rt_types_response = requests.get(rt_types_url)
        if rt_types_response.status_code != 200:
            return {"title": "error", "message": "Failed to get repair time types", "details": rt_types_response.text}
        repairtime_types = rt_types_response.json()
        if not repairtime_types or not isinstance(repairtime_types, list):
            return {"title": "error", "message": "No repair time types found", "details": repairtime_types}
        target_repairtime_type_id = repairtime_types[0]['repairtimeTypeId']
        type_category = repairtime_types[0].get('typeCategory', 'CAR')

        # 4) Build full tree recursively from root
        tree = build_full_repair_tree(
            vrid=vrid,
            repairtime_type_id=target_repairtime_type_id,
            type_category=type_category,
            description_language="en",
            root_node_id="root"
        )

        # 5) Save JSON file
        json_path = save_tree_json(tree, job_data.vin)

        return {
            "vrid": vrid,
            "car_type_id": car_type_id,
            "target_repairtime_type_id": target_repairtime_type_id,
            "type_category": type_category,
            "tree_structure": tree,
            "json_path": json_path,
            "api_call_count": tree.get("api_call_count", 0)
        }
    except Exception as e:
        print(e)
        print(traceback.format_exc())
        return {"title":"error"}
 
@app.post("/node-search")
def node_search(job_data: NodeSearchJobData):
    try:
        repairtime_infos_url = f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/getRepairtimeSubnodesByGroupV4?vrid={job_data.vrid}&descriptionLanguage=en&repairtimeTypeId={job_data.target_repairtime_type_id}&typeCategory={job_data.type_category}&nodeId={job_data.nodeId}"
        print(f"repairtime infos url: {repairtime_infos_url}")
        #log_api_call("haynes-pro", job_data.tenant, job_data.vin, repairtime_infos_url)
        response = requests.get(repairtime_infos_url)
        repairtime_infos = response.json()
        return {
            "groups": repairtime_infos
        }
    except Exception as e:
        print(e)
        print(traceback.format_exc())
        return {"title":"error"}

def check_maintenance_period(maintenance_tasks: dict, days_since_last_service: int, mileage: int) -> dict:
    """
    Filter maintenance tasks based on time/mileage requirements in remarks.
    
    Rules:
    - If requirement is fully met: includeasdefault = True, keep task
    - If requirement is 70%+ met but not fully: includeasdefault = False, keep task
    - Otherwise: remove task
    """
    months_since_last_service = days_since_last_service / 30.0
    filtered_tasks = []
    
    for task in maintenance_tasks.get("subTasks", []):
        remark = task.get("remark", "").lower()
        keep_task = False
        include_as_default = False
        
        # Check month requirements
        month_matches = re.findall(r'(\d+)\s*months?', remark)
        if month_matches:
            required_months = int(month_matches[0])
            if months_since_last_service >= required_months:
                # Fully met requirement
                keep_task = True
                include_as_default = True
            elif months_since_last_service >= (required_months * 0.7):
                # 70%+ met but not fully
                keep_task = True
                include_as_default = False
        
        # Check mile requirements
        mile_matches = re.findall(r'(\d+)\s*miles?', remark)
        if mile_matches:
            required_miles = int(mile_matches[0])
            if mileage >= required_miles:
                # Fully met requirement
                keep_task = True
                include_as_default = True
            elif mileage >= (required_miles * 0.7):
                # 70%+ met but not fully
                keep_task = True
                include_as_default = False
        
        # If no time/mileage requirements found in remark, keep the task with default behavior
        if not month_matches and not mile_matches:
            keep_task = True
            include_as_default = task.get("includeasdefault", False)
        
        if keep_task:
            # Update the task with the calculated includeasdefault value
            task_copy = task.copy()
            task_copy["includeasdefault"] = include_as_default
            filtered_tasks.append(task_copy)
    
    # Return the filtered maintenance tasks structure
    result = maintenance_tasks.copy()
    result["subTasks"] = filtered_tasks
    return result

@app.post("/haynes-pro-v2")
def haynes_pro_v2(job_data: HaynesProJobData):
    try:
        results_list = []
        auth_url = f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/getAuthenticationVrid?distributorUsername={HAYNES_PRO_USERNAME}&distributorPassword={HAYNES_PRO_PASSWORD}&username=jnpda2025"
        #log_api_call("haynes-pro-v2", job_data.tenant, job_data.vin, auth_url)
        response = requests.get(auth_url)
        if response.json()["statusCode"] == 0:
            vrid = response.json()["vrid"]
        else:
            print(response.text)
            exit()
            
        vin_decode_url = f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/decodeVINV4?vrid={vrid}&vin={job_data.vin}&descriptionLanguage=en"
        #log_api_call("haynes-pro-v2", job_data.tenant, job_data.vin, vin_decode_url)
        vin_decode_response = requests.get(vin_decode_url)
        if vin_decode_response.status_code != 200:
            print(f"Haynes Pro VIN decoding failed: {vin_decode_response.text}")
            return {"error": "Haynes Pro VIN decoding failed", "details": vin_decode_response.text}
        vehicle_info_list = vin_decode_response.json()
        if not vehicle_info_list or not isinstance(vehicle_info_list, list) or not vehicle_info_list[0].get("id"):
            print(f"Invalid vehicle info from VIN decode: {vehicle_info_list}")
            return {"error": "Invalid vehicle info from Haynes Pro", "details": vehicle_info_list}
        car_type_id = vehicle_info_list[0]["id"]
        #print(vehicle_info_list[0]["subjects"])
        print(f"car type id: {car_type_id}")
            
        if "full service" in job_data.workItems[0].title.lower():
            maintenance_system_url = f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/getMaintenanceSystemsV7?vrid={vrid}&descriptionLanguage=en&carTypeId={car_type_id}&typeCategory=CAR&countryCodes=gb&useImperial=true&includeServiceTimes=true"
            response = requests.get(maintenance_system_url)
            maintenance_systems = response.json()
            system_id = maintenance_systems[0]["id"]
            maintenance_periods = {period["id"]:period["name"] for period in maintenance_systems[0]["maintenancePeriods"]}
            print(f"maintenance systems: {maintenance_systems}")
            client = genai.Client(api_key=GEMINI_API_KEY)

            days_since_last_service = (datetime.now() - datetime.strptime(job_data.last_service_date, "%Y-%m-%d")).days
            
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=f"given the following maintenance periods: {maintenance_periods}, and given the vehicle has {job_data.mileage} miles and its last service was {days_since_last_service} days ago, return the most appropriate maintenance period. Return only the id and name of the maintenance period in a json format.",
            )
            print(response.text)
            import json
            maintenance_period_id = response.text.split("```json")[1].split("```")[0]
            json_response = json.loads(maintenance_period_id)
            period_name = json_response['name']
            print(f"maintenance period id: {json_response}")
            
            maintenance_tasks_url = f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/getMaintenanceTasksV9?vrid={vrid}&descriptionLanguage=en&carTypeId={car_type_id}&systemId={system_id}&periodId={json_response['id']}&includeSmartLinks=false&includeServiceTimes=true"
            #log_api_call("haynes-pro-v2", job_data.tenant, job_data.vin, maintenance_tasks_url)
            response = requests.get(maintenance_tasks_url)
            maintenance_tasks = response.json()
            maintenance_tasks = check_maintenance_period(maintenance_tasks, days_since_last_service, job_data.mileage)
            #print(f"maintenance tasks: {maintenance_tasks}")
            results_list.append({"car_type_id": car_type_id, "system_id": system_id, "period_id": json_response['id'], "maintenance_tasks": maintenance_tasks, "period_name": json_response['name']})
            return {
            "results": results_list,
            "tree_structure": {},
            "matched_work_items": {}
        }
        else:
            print("No full service in job data")
            return repair_tasks(job_data, vrid, car_type_id)
            exit()
    except Exception as e:
        print(e)
        print(traceback.format_exc())
        return {"title":"error"}
    return {"title":"success"}

    

@app.post("/repair-instructions")
def repair_instructions(job_data: RepairInstructionsJobData):
    try:
        auth_url = f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/getAuthenticationVrid?distributorUsername={HAYNES_PRO_USERNAME}&distributorPassword={HAYNES_PRO_PASSWORD}&username=jnpda2025"
        log_api_call("repair-instructions", job_data.tenant, job_data.vin, auth_url)
        response = requests.get(auth_url)
        if response.json()["statusCode"] == 0:
            vrid = response.json()["vrid"]
        else:
            print(response.text)
            exit()
        
        results_list = []
        for repair_task_id in job_data.repairTaskIds:
            repair_infos_url = f"https://www.haynespro-services.com/workshopServices3/rest/jsonendpoint/getRepairtimeInfosV4?vrid={vrid}&descriptionLanguage=en&repairtimeTypeId={job_data.target_repairtime_type_id}&typeCategory={job_data.type_category}&repairTaskId={repair_task_id}"
            log_api_call("repair-instructions", job_data.tenant, job_data.vin, repair_infos_url)
            response = requests.get(repair_infos_url)
            repairtime_infos = response.json()
            print(f"repairtime infos: {repairtime_infos}")
            results_list.append({"repair_task_id": repair_task_id, "repairtime_infos": repairtime_infos})
    except Exception as e:
        print(e)
        print(traceback.format_exc())
        return {"title":"error"}
    return {
        "results": results_list,
        "tree_structure": tree_structure,
        "matched_work_items": matched_work_items
    }


def get_supported_brands(input_brand):
    supported_brands = {"brands":["Alpine","Audi","Bentley","BMW","BMWMotorrad","Seat","Dacia","Jaguar","LandRover","Mercedes","MercedesTrucks","MercedesUnimog","MercedesVans","Mini","Mitsubishi","MAN","Porsche","PorscheClassic","Renault","Seat","Skoda","Smart","VW","VWCommercial","Toyota","Lexus","Suzuki"]}
    brands_list = supported_brands.get("brands", [])
    for brand in brands_list:
        if input_brand.lower() == brand.lower():
            return brand
        elif input_brand.lower() == "vw" or input_brand.lower() == "volkswagen":
            return "VW"
    return None

@app.post("/partslink24")
def partslink24(job_data: PartsLink24JobData):
    brand = get_supported_brands(job_data.brand)
    if brand is None:
        return {"title":"error", "message":"Brand not supported"}
    
    
    BASE_URL = "https://demo.partslink24.com/pl24-orderbrg/ext/"

    # Authentication (Basic Auth)
    USERNAME = "orderbridge-combine-gb"
    PASSWORD = "jcL2(733dt"
    AUTH = (USERNAME, PASSWORD)
    
    order_submission_url = f"{BASE_URL}api/1.0/order-submissions"
    headers = {
        "Accept-Language": "EN",
        "Content-Type": "application/xml" # Explicitly set Content-Type for XML
    }
    
    print(f"--- EXT order-submissions {job_data.brand}  ---")
    part_items = ""
    externalID = 1
    for part in job_data.workItems:
        # Check if part has partnumbers list and handle accordingly
        if hasattr(part, 'part_numbers') and part.part_numbers:
            # Create a partItem for each part number
            for part_number in part.part_numbers:
                part_items += f"""  <partItem externalID="{externalID}" activity="rep{externalID}">
            <description>{part.invoice_description[:20]}</description>
            <partNumber>{part_number}</partNumber>
            <quantity>1</quantity>
        </partItem>"""
                externalID += 1
        else:
            # If no part numbers or empty list, use "unknown"
            part_items += f"""<partItem externalID="{externalID}" activity="rep{externalID}">
            <description>{part.invoice_description[:20]}</description>
            <partNumber>unknown</partNumber>
            <quantity>1</quantity>
        </partItem>\n"""
            externalID += 1
        
    xml_body_order_submission = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <orderSubmission externalID="Reparatur001">
        <externalSystem>
            <user>Extern User</user>
            <name>combine systems</name>
            <country>GB</country>
            <language>en</language>
            <tenant>Test Dealership</tenant>
        </externalSystem>
        <history>
        </history>
        <orderData>
            <brand>{brand}</brand>
            <vin>{job_data.vin}</vin>
            <partItems>
                {part_items}
            </partItems>
            <labourItems>
            </labourItems>
            <paintItems>
            </paintItems>    </orderData>
    </orderSubmission>"""
    print(xml_body_order_submission)
    try:
        log_api_call("partslink24", job_data.tenant, job_data.vin, order_submission_url, "POST")
        response = requests.post(order_submission_url, headers=headers, data=xml_body_order_submission, auth=AUTH)
        response.raise_for_status()
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    print("\n")
    
    import xml.etree.ElementTree as ET

    # Parse the XML string
    root = ET.fromstring(response.text)

    # Find the accessToken element and get its text
    access_token = root.find('accessToken').text

    print(f"Access Token: {access_token}")
    
    # EXT entry-points
    print("--- EXT entry-points ---")
    entry_points_url = f"{BASE_URL}api/1.0/entry-points/{access_token}"
    headers_json = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    try:
        log_api_call("partslink24", job_data.tenant, job_data.vin, entry_points_url)
        response = requests.get(entry_points_url, headers=headers_json, auth=AUTH)
        response.raise_for_status()
        print(f"Status Code: {response.status_code}")
        print(f"Response Body (JSON): {response.json()}")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    print("\n")
    
    return {"title":"success"}

    
    
@app.get("/")
def read_root():
    return {"message": "Welcome to the JobNPart Backend API"}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)



