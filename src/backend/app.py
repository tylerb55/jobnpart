from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import uvicorn
from google import genai
import requests
from requests.auth import HTTPBasicAuth
import os
from schemas import *
from dotenv import load_dotenv
from annoy import AnnoyIndex
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi
import numpy as np
from contextlib import asynccontextmanager
import logging
import traceback
from supabase import create_client, Client
from datetime import datetime
import json
import re
import asyncio
from threading import Timer
import aiohttp
import pickle
import tempfile
import sys

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("PARTS_CATALOG_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HAYNES_PRO_USERNAME = os.getenv("HAYNES_PRO_USERNAME")
HAYNES_PRO_PASSWORD = os.getenv("HAYNES_PRO_PASSWORD")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
QUOTE_API_USERNAME = os.getenv("QUOTE_API_USERNAME")
QUOTE_API_PASSWORD = os.getenv("QUOTE_API_PASSWORD")
PARTS_SEARCH_AVAILABLE = os.getenv("PARTS_SEARCH_AVAILABLE")
VECTOR_DIMENSION = 768
METRIC = 'angular' # Common metric for semantic similarity (cosine similarity)
NUM_TREES = 10     # Higher number of trees gives better precision but slower indexing

# API Request Configuration
MAX_CONCURRENT_CONNECTIONS = 20  # Maximum total concurrent connections
MAX_CONNECTIONS_PER_HOST = 10    # Maximum concurrent connections per host
REQUEST_TIMEOUT_SECONDS = 90     # Timeout for individual API requests
MAX_RETRIES = 3                  # Maximum retry attempts for failed requests
BATCH_SIZE = 50                  # Maximum concurrent DFS traversals


# Initialize Supabase client with service role key (bypasses RLS for backend operations)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY)

# Global variable to store the bearer token
bearer_token: Optional[str] = None
global REPAIR_TASKS
global REPAIR_DESCRIPTIONS
global bm25
global annoy_index
global full_repair_tree

def pickle_object(obj, filename):
    """Serializes a Python object to a file."""
    with open(filename, 'wb') as f:
        pickle.dump(obj, f)
    print(f"\nSuccessfully pickled object to '{filename}'.")

def unpickle_object(filename):
    """Deserializes a Python object from a file."""
    with open(filename, 'rb') as f:
        obj = pickle.load(f)
    print(f"Successfully unpickled object from '{filename}'.")
    return obj

def upload_to_supabase(file_path: str) -> bool:
    """
    Upload a file to Supabase storage.
    
    Args:
        file_path: Path to the file to upload
        
    Returns:
        True if successful, False otherwise
        
    Raises:
        ValueError: If file type is not supported
        RuntimeError: If upload fails
    """
    # Determine MIME type based on file extension
    mime_type_map = {
        ".json": "application/json",
        ".pkl": "application/octet-stream",
        ".ann": "application/octet-stream"
    }
    
    file_ext = os.path.splitext(file_path)[1]
    mime_type = mime_type_map.get(file_ext)
    
    if not mime_type:
        error_msg = f"Unsupported file type: {file_path}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    try:
        # Determine storage path based on file extension
        storage_folder = file_ext.lstrip(".")
        storage_path = f"{storage_folder}/{file_path}"
        
        with open(file_path, "rb") as f:
            response = supabase.storage.from_("repair_tasks").upload(
                file=f,
                path=storage_path,
                file_options={
                    "content-type": mime_type, 
                    "cache-control": "3600", 
                    "upsert": "true"
                }
            )
        
        logger.info(f"Successfully uploaded {file_path} to Supabase at {storage_path}")
        return True
        
    except FileNotFoundError as e:
        logger.error(f"File not found for upload: {file_path}")
        raise RuntimeError(f"Cannot upload non-existent file: {file_path}") from e
        
    except Exception as e:
        logger.error(f"Error uploading file {file_path} to Supabase: {e}")
        logger.error(traceback.format_exc())
        raise RuntimeError(f"Failed to upload {file_path}: {str(e)}") from e
    
def download_from_supabase(vrm: str):
    """
    Download and load cached repair tree data from Supabase storage.
    
    Args:
        vrm: Vehicle Registration Mark
        
    Returns:
        Tuple of (full_repair_tree, annoy_index, bm25) if successful
        
    Raises:
        FileNotFoundError: If the VRM data is not found in Supabase
        RuntimeError: If download or loading fails for other reasons
    """
    global REPAIR_TASKS, REPAIR_DESCRIPTIONS, annoy_index, bm25, full_repair_tree
    
    temp_files = []
    
    try:
        logger.info(f"Downloading repair tree data for VRM: {vrm} from Supabase")
        
        # Download repair tree
        tree_file = f"{vrm}_repair_tree.json"
        supabase.storage.from_("repair_tasks").download(f"json/{tree_file}")
        temp_files.append(tree_file)
        with open(tree_file, "r") as f:
            full_repair_tree = json.load(f)
        
        # Download repair tasks
        tasks_file = f"{vrm}_repair_tasks.json"
        supabase.storage.from_("repair_tasks").download(f"json/{tasks_file}")
        temp_files.append(tasks_file)
        with open(tasks_file, "r") as f:
            json_repair_tasks = json.load(f)
        REPAIR_TASKS = json_repair_tasks["tasks"]
        REPAIR_DESCRIPTIONS = json_repair_tasks["descriptions"]
        
        # Download Annoy index
        annoy_file = f"{vrm}_annoy_index.ann"
        supabase.storage.from_("repair_tasks").download(f"ann/{annoy_file}")
        temp_files.append(annoy_file)
        annoy_index = AnnoyIndex(VECTOR_DIMENSION, METRIC)
        annoy_index.load(annoy_file)
        
        # Download BM25 index
        bm25_file = f"{vrm}_bm25.pkl"
        supabase.storage.from_("repair_tasks").download(f"pkl/{bm25_file}")
        temp_files.append(bm25_file)
        with open(bm25_file, "rb") as f:
            bm25 = pickle.load(f)
        
        logger.info(f"Successfully loaded cached data for VRM: {vrm}")
        return full_repair_tree, annoy_index, bm25
        
    except Exception as e:
        error_msg = str(e)
        
        # Check if it's a 404/not found error
        if "not found" in error_msg.lower() or "404" in error_msg:
            logger.info(f"No cached data found for VRM: {vrm}")
            raise FileNotFoundError(f"No cached repair tree found for VRM: {vrm}") from e
        
        # Other errors
        logger.error(f"Error downloading data from Supabase for VRM {vrm}: {e}")
        logger.error(traceback.format_exc())
        raise RuntimeError(f"Failed to download repair tree from Supabase: {error_msg}") from e
        
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file {temp_file}: {e}")
    
def log_haynes_pro_request(tenant_code: str,
    service: str,
    vin: str,
    base_url: str,
    full_url: str,
    timestamp: str,
    api_key: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Sends a POST request to the InsertApiLog endpoint to create a new log entry.

    Args:
        tenant_code: The tenant code (e.g., "qpg-test").
        service: The service name (e.g., "Full Service").
        vin: The Vehicle Identification Number.
        base_url: The base URL of the request.
        full_url: The full URL of the request.
        timestamp: The timestamp of the log entry (ISO 8601 format, e.g., "2025-03-07T15:50:00").
        api_key: Optional API key. Uses the default key if None.

    Returns:
        A dictionary containing the response JSON (e.g., {"id": "..."}) 
        or None if the request fails.
    """
    
    URL = "https://tablet-beta.moxhamconsultants.com:3131/PartsApis/InsertApiLog"
    DEFAULT_API_KEY = os.getenv("TOBY_API_KEY")
    
    # Use the provided key or the default
    key_to_use = api_key if api_key else DEFAULT_API_KEY
    
    # 2. Construct the request headers
    # Content-Type is important to tell the server the body is JSON
    # The API Key is sent in the custom 'ApiKey' header
    headers = {
        "ApiKey": key_to_use,
        "Content-Type": "application/json",
        "Accept": "*/*",
        # Including a User-Agent is good practice, mimicking a known client if necessary
        "User-Agent": "PythonRequestsScript" 
    }
    
    # 3. Construct the JSON payload
    payload = {
        "tenantCode": tenant_code,
        "service": service,
        "vin": vin,
        "base_url": base_url,
        "full_url": full_url,
        "timestamp": timestamp
    }
    
    print(f"Attempting to log data to {URL}...")
    
    try:
        # 4. Send the POST request
        # The 'json=' parameter in requests automatically serializes the dictionary
        # to a JSON string and sets the Content-Type header to application/json
        response = requests.post(URL, headers=headers, json=payload, timeout=10)

        # 5. Check for a successful response status code (e.g., 201 Created)
        response.raise_for_status() 
        # If the response status is 4xx or 5xx, this line will raise an HTTPError

        # 6. Parse and return the JSON response
        log_id = response.json()
        print(f"Successfully created log. Log ID: {log_id.get('id')}")
        return log_id

    except requests.exceptions.RequestException as e:
        # Handle various request errors (connection, timeout, HTTP status errors)
        print(f"An error occurred while sending the POST request: {e}")
        # Print the response text for more details if an HTTP error occurred
        if 'response' in locals() and hasattr(response, 'text'):
            print(f"Server response (if available): {response.text}")
        return None
    except json.JSONDecodeError:
        print("Error: Received a successful status code but the response was not valid JSON.")
        return None

def auth() -> str:
    """
    Authentication function that returns a bearer token.
    This function is called on server startup and every 23 hours.
    Currently empty - to be implemented with actual authentication logic.
    """
    global bearer_token
    global GLOBAL_HEADERS
    global DOMAIN
    global gen_model 
    global full_repair_tree
    global model
    global bm25
    global annoy_index
    
    
    gen_model = genai.Client(api_key=GEMINI_API_KEY)
    DOMAIN = "https://apiuat.haynesquoteengine.co.uk"
    auth_url = f"{DOMAIN}/api/v1/authenticate"
    auth_headers = {
        "applicationId": "35"
    }

    try:
        response = requests.get(auth_url, headers=auth_headers, auth=HTTPBasicAuth(QUOTE_API_USERNAME, QUOTE_API_PASSWORD))
        try:
            json_response = response.json()
            print("Response Body (JSON):", json.dumps(json_response, indent=2))
            token = json_response["token"]
        except json.JSONDecodeError:
            print("Response Body (Text):", response.text)
            token = response.text
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        if 'response' in locals() and response is not None:
             print(f"Error Response Body: {response.text}")
        token = None

    bearer_token = token
    GLOBAL_HEADERS = {"Authorization": f"Bearer {bearer_token}","Content-Type": "application/json"}
    print(f"Auth function called - token updated: {bearer_token}")
    return token

def schedule_auth_refresh():
    """
    Schedule the next auth refresh in 23 hours.
    """
    def refresh_and_reschedule():
        auth()
        schedule_auth_refresh()
    
    # Schedule next refresh in 23 hours (23 * 60 * 60 seconds)
    timer = Timer(23 * 60 * 60, refresh_and_reschedule)
    timer.daemon = True  # Dies when main thread dies
    timer.start()
    print("Auth refresh scheduled for 23 hours from now")

@asynccontextmanager
async def lifespan(_: FastAPI):
    print("Starting up...")
    global model
    model = SentenceTransformer('intfloat/e5-base-v2')
    
    # Call auth function on startup and schedule periodic refresh
    auth()
    schedule_auth_refresh()
    
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

    
def tokenize(text: str) -> List[str]:
    """
    Simple tokenizer that converts text to lowercase and splits on word boundaries.
    """
    # Convert to lowercase and split on non-alphanumeric characters
    tokens = re.findall(r'\w+', text.lower())
    return tokens

def search_bm25(query_text: str, bm25_index: BM25Okapi, top_k: int = 10) -> List[Dict]:
    """
    Performs a keyword-based BM25 search.
    
    Args:
        query_text: The search query
        bm25_index: The BM25 index
        top_k: Number of top results to return
    
    Returns:
        List of dictionaries containing index, awNumber, description, and BM25 score
    """
    global REPAIR_TASKS, REPAIR_DESCRIPTIONS
    
    # Tokenize the query
    tokenized_query = tokenize(query_text)
    
    # Get BM25 scores for all documents
    scores = bm25_index.get_scores(tokenized_query)
    
    # Get top-k indices
    top_indices = np.argsort(scores)[::-1][:top_k]
    
    # Format results
    results = []
    print(REPAIR_TASKS)
    for idx in top_indices:
        results.append({
            "index": int(idx),
            "awNumber": REPAIR_TASKS[idx]["awNumber"],
            "description": REPAIR_DESCRIPTIONS[idx],
            "bm25_score": float(scores[idx])
        })
    
    return results

def search_annoy_index(query_text, annoy_index, model, top_k=2):
    """
    Performs a semantic search against the in-memory Annoy index.
    """
    global REPAIR_TASKS, REPAIR_DESCRIPTIONS
    
    # 1. Convert the query text into a vector using the same model
    query_vector = model.encode(query_text)

    # 2. Perform the Approximate Nearest Neighbors (ANN) Search
    # get_nns_by_vector returns the internal IDs (indices) and their distances
    # n=top_k specifies how many nearest neighbors to retrieve
    indices, distances = annoy_index.get_nns_by_vector(
        query_vector, 
        n=top_k, 
        include_distances=True
    )

    # 3. Format Results
    results = []
    for index, distance in zip(indices, distances):
        results.append({
            "index": index,
            "awNumber": REPAIR_TASKS[index]["awNumber"],
            "description": REPAIR_DESCRIPTIONS[index],
            "similarity_score": round(1 - distance**2 / 2, 4) # Convert angular distance to cosine similarity
        })
        
    return results

def _build_search_indexes(vrm: str, repair_descriptions: List[str]) -> tuple[BM25Okapi, AnnoyIndex]:
    """
    Build BM25 and Annoy search indexes from repair descriptions.
    
    Args:
        vrm: Vehicle Registration Mark
        repair_descriptions: List of repair task descriptions
        
    Returns:
        Tuple of (bm25_index, annoy_index)
        
    Raises:
        ValueError: If descriptions are empty or invalid
        RuntimeError: If index building fails
    """
    if not repair_descriptions:
        raise ValueError("Cannot build indexes with empty descriptions")
    
    try:
        # Build BM25 index with robust tokenization
        tokenized_descriptions = []
        for desc in repair_descriptions:
            parts = desc.split(" -> ")
            if len(parts) >= 2:
                tokenized_descriptions.append(tokenize(parts[-2]))
            else:
                tokenized_descriptions.append(tokenize(parts[-1] if parts else ""))
        
        bm25_index = BM25Okapi(tokenized_descriptions)
        logger.info(f"Built BM25 index with {len(tokenized_descriptions)} descriptions")
        
        # Build Annoy index
        vectors = model.encode(repair_descriptions)
        annoy_idx = AnnoyIndex(VECTOR_DIMENSION, METRIC)
        
        for i, vector in enumerate(vectors):
            annoy_idx.add_item(i, vector)
        
        annoy_idx.build(NUM_TREES)
        logger.info(f"Built Annoy index with {len(vectors)} vectors")
        
        return bm25_index, annoy_idx
        
    except Exception as e:
        logger.error(f"Failed to build search indexes: {e}")
        logger.error(traceback.format_exc())
        raise RuntimeError(f"Index building failed: {str(e)}") from e


def _save_repair_tree_artifacts(vrm: str, root_node_structure: dict, 
                                repair_tasks: List[dict], repair_descriptions: List[str],
                                bm25_index: BM25Okapi, annoy_idx: AnnoyIndex) -> List[str]:
    """
    Save all repair tree artifacts to files and upload to Supabase.
    
    Args:
        vrm: Vehicle Registration Mark
        root_node_structure: The complete repair tree structure
        repair_tasks: List of repair tasks
        repair_descriptions: List of repair descriptions
        bm25_index: BM25 search index
        annoy_idx: Annoy search index
        
    Returns:
        List of created file paths for cleanup
        
    Raises:
        IOError: If file operations fail
    """
    created_files = []
    
    try:
        # Save repair tasks
        tasks_file = f"{vrm}_repair_tasks.json"
        with open(tasks_file, "w") as f:
            json.dump({"tasks": repair_tasks, "descriptions": repair_descriptions}, f)
        created_files.append(tasks_file)
        upload_to_supabase(tasks_file)
        
        # Save Annoy index
        annoy_file = f"{vrm}_annoy_index.ann"
        annoy_idx.save(annoy_file)
        created_files.append(annoy_file)
        upload_to_supabase(annoy_file)
        
        # Save BM25 index
        bm25_file = f"{vrm}_bm25.pkl"
        pickle_object(bm25_index, bm25_file)
        created_files.append(bm25_file)
        upload_to_supabase(bm25_file)
        
        # Save repair tree
        tree_file = f"{vrm}_repair_tree.json"
        with open(tree_file, "w") as f:
            json.dump(root_node_structure, f)
        created_files.append(tree_file)
        upload_to_supabase(tree_file)
        
        logger.info(f"Successfully saved all artifacts for VRM: {vrm}")
        return created_files
        
    except Exception as e:
        logger.error(f"Failed to save artifacts: {e}")
        logger.error(traceback.format_exc())
        raise IOError(f"Failed to save repair tree artifacts: {str(e)}") from e


def _cleanup_temp_files(file_paths: List[str]) -> None:
    """Remove temporary files, logging any failures."""
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Cleaned up temp file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {file_path}: {e}")


def _validate_repair_descriptions(repair_tasks: List[dict], repair_descriptions: List[str]) -> None:
    """Log warnings for descriptions that don't follow expected format."""
    logger.info(f"Validating {len(repair_descriptions)} repair descriptions")
    
    for idx, desc in enumerate(repair_descriptions):
        parts = desc.split(" -> ")
        if len(parts) < 2:
            logger.warning(
                f"Description at index {idx} has only {len(parts)} part(s): "
                f"'{desc}' (awNumber: {repair_tasks[idx]['awNumber']})"
            )


@app.post("/create-tree-async")
async def build_full_repair_tree(data: CreateTreeJobData) -> dict:
    """
    Recursively traverse all subnodes starting from root and return the entire tree structure.
    Uses async/await with parallel API calls for dramatic performance improvement.
    
    Workflow:
    1. Attempt to load cached tree from Supabase
    2. If not found, build tree from scratch via API calls
    3. Create search indexes (BM25 and Annoy)
    4. Save artifacts to Supabase
    
    Args:
        data: CreateTreeJobData containing vrm and tenant information
        
    Returns:
        Complete repair tree structure as dictionary
        
    Raises:
        HTTPException: 400 for validation errors, 500 for server errors
    """
    global api_call_count, REPAIR_TASKS, REPAIR_DESCRIPTIONS, bm25, annoy_index, full_repair_tree
    
    api_call_count = 0
    temp_files = []
    
    try:
        # Validate input
        if not data.vrm or not data.vrm.strip():
            raise HTTPException(status_code=400, detail="VRM is required")
        
        logger.info(f"Building repair tree for VRM: {data.vrm}")
        
        # Attempt to load from cache
        try:
            logger.info(f"Attempting to load cached tree for VRM: {data.vrm}")
            cached_tree, cached_annoy, cached_bm25 = download_from_supabase(data.vrm)
            
            if cached_tree:
                full_repair_tree = cached_tree
                annoy_index = cached_annoy
                bm25 = cached_bm25
                logger.info(f"Successfully loaded cached tree for VRM: {data.vrm}")
                return cached_tree
                
        except Exception as e:
            logger.info(f"Cache miss for VRM {data.vrm}, building from scratch: {e}")
        
        # Build tree from scratch
        logger.info(f"Building repair tree from API for VRM: {data.vrm}")
        
        root_node_structure = {
            "awNumber": "root",
            "description": "Root Node",
            "parentNodeId": None,
            "childTasks": []
        }
        
        # Fetch tree structure via async API calls
        try:
            # Configure session with connection limits to prevent overwhelming the server
            connector = aiohttp.TCPConnector(
                limit=MAX_CONCURRENT_CONNECTIONS,
                limit_per_host=MAX_CONNECTIONS_PER_HOST,
                ttl_dns_cache=300  # DNS cache TTL in seconds
            )
            
            timeout = aiohttp.ClientTimeout(total=None)  # No total timeout for the session
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                root_node_structure["childTasks"] = await _dfs_async(
                    "root", "", data.vrm, data.tenant, session
                )
        except Exception as e:
            logger.error(f"Failed to fetch repair tree from API: {e}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch repair tree from external API: {str(e)}"
            ) from e
        
        # Extract and validate tasks
        try:
            REPAIR_TASKS = extract_tasks_dfs(root_node_structure.get("childTasks", []))
            REPAIR_DESCRIPTIONS = [task["description"] for task in REPAIR_TASKS]
            
            if not REPAIR_TASKS:
                logger.warning(f"No repair tasks found for VRM: {data.vrm}")
                return root_node_structure
            
            _validate_repair_descriptions(REPAIR_TASKS, REPAIR_DESCRIPTIONS)
            
        except Exception as e:
            logger.error(f"Failed to extract repair tasks: {e}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process repair tasks: {str(e)}"
            ) from e
        
        # Build search indexes
        try:
            bm25, annoy_index = _build_search_indexes(data.vrm, REPAIR_DESCRIPTIONS)
        except Exception as e:
            logger.error(f"Failed to build search indexes: {e}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Failed to build search indexes: {str(e)}"
            ) from e
        
        # Save artifacts
        try:
            temp_files = _save_repair_tree_artifacts(
                data.vrm, root_node_structure, REPAIR_TASKS, 
                REPAIR_DESCRIPTIONS, bm25, annoy_index
            )
        except Exception as e:
            logger.error(f"Failed to save artifacts: {e}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save repair tree artifacts: {str(e)}"
            ) from e
        
        full_repair_tree = root_node_structure
        logger.info(f"Successfully built and saved repair tree for VRM: {data.vrm}")
        
        return root_node_structure
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
        
    except Exception as e:
        # Catch any unexpected errors
        logger.error(f"Unexpected error in build_full_repair_tree: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        ) from e
        
    finally:
        # Clean up temporary files
        if temp_files:
            _cleanup_temp_files(temp_files)


async def _fetch_repair_subnodes_async(
    vrm: str, 
    awnumber: str, 
    tenant: str, 
    session: aiohttp.ClientSession,
    max_retries: int = MAX_RETRIES,
    timeout_seconds: int = REQUEST_TIMEOUT_SECONDS
) -> list:
    """
    Async version: Fetch one level of subnodes for a given nodeId with retry logic.
    
    Args:
        vrm: Vehicle Registration Mark
        awnumber: AW number of the node to fetch subnodes for
        tenant: Tenant identifier
        session: Aiohttp session for connection pooling
        max_retries: Maximum number of retry attempts
        timeout_seconds: Timeout in seconds for each request
        
    Returns:
        List of subnodes, or empty list if fetch fails after all retries
    """
    global api_call_count
    api_call_count += 1
    
    subnodes_url = f"https://apiuat.haynesquoteengine.co.uk/api/v1/RepairTree/{vrm}/Layer/{awnumber}"
    log_haynes_pro_request(
        tenant, 
        "Repair Tree Subnodes (Building repair tree)", 
        vrm, 
        f"{DOMAIN}", 
        subnodes_url, 
        datetime.now().isoformat()
    )
    
    # Retry logic with exponential backoff
    for attempt in range(max_retries):
        try:
            timeout = aiohttp.ClientTimeout(
                total=timeout_seconds,
                connect=10,  # 10 seconds to establish connection
                sock_read=timeout_seconds - 10  # Remaining time for reading data
            )
            
            async with session.get(subnodes_url, headers=GLOBAL_HEADERS, timeout=timeout) as response:
                response.raise_for_status()
                data = await response.json()
                
                # Log success if it took multiple attempts
                if attempt > 0:
                    logger.info(f"Successfully fetched subnodes for {awnumber} on attempt {attempt + 1}")
                
                return data
                
        except aiohttp.ClientResponseError as e:
            if e.status == 429:  # Rate limit
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                logger.warning(f"Rate limited for {awnumber}, waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                await asyncio.sleep(wait_time)
                continue
            elif e.status >= 500:  # Server error
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Server error {e.status} for {awnumber}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    continue
            
            logger.error(f"HTTP error fetching subnodes for {awnumber}: {e.status} - {e.message}")
            logger.error(traceback.format_exc())
            return []
            
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            error_type = "Timeout" if isinstance(e, asyncio.TimeoutError) else "Network error"
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.warning(
                    f"{error_type} fetching subnodes for {awnumber}, "
                    f"retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(wait_time)
                continue
            else:
                logger.error(f"{error_type} fetching subnodes for {awnumber} after {max_retries} attempts: {e}")
                logger.error(traceback.format_exc())
                return []
                
        except Exception as e:
            logger.error(f"Unexpected error fetching subnodes for {awnumber}: {e}")
            logger.error(traceback.format_exc())
            return []
    
    # If we exhausted all retries
    logger.error(f"Failed to fetch subnodes for {awnumber} after {max_retries} attempts")
    return []

async def _dfs_async(
    node_id: str, 
    path: str, 
    vrm: str, 
    tenant: str, 
    session: aiohttp.ClientSession,
    semaphore: Optional[asyncio.Semaphore] = None,
    batch_size: int = BATCH_SIZE
) -> List[Dict[str, Any]]:
    """
    Async helper DFS function to recursively fetch and build the subtree for a given node_id.
    Fetches all sibling nodes in parallel with controlled concurrency.
    
    Args:
        node_id: The ID of the node whose direct children are to be fetched.
        path: The path taken to get to the current node.
        vrm: The VRM parameter for the API call.
        tenant: Tenant identifier
        session: Aiohttp session for connection pooling.
        semaphore: Optional semaphore to control concurrency (created if None)
        batch_size: Maximum number of concurrent child fetches

    Returns:
        A list of dictionaries, where each dictionary is a child node with its full subtree.
    """
    
    # Create semaphore if not provided (at root level)
    if semaphore is None:
        semaphore = asyncio.Semaphore(batch_size)
    
    # 1. Fetch direct subnodes for the current node_id
    child_tasks_data = await _fetch_repair_subnodes_async(vrm, node_id, tenant, session)
    
    # 2. Initialize the list to hold the structured child nodes
    structured_children: List[Dict[str, Any]] = []

    # 3. Process each direct subnode and prepare async tasks for children with subnodes
    async_tasks = []
    nodes_with_tasks = []
    
    for task in child_tasks_data:
        # Create the node structure
        node = {
            "awNumber": task["awNumber"],
            "description": path + " -> " + task["description"],
            "parentNodeId": node_id,
            "childTasks": []
        }
        
        structured_children.append(node)
        
        # 4. If this node has children, prepare an async task to fetch them in parallel
        if task["hasChildren"]:
            nodes_with_tasks.append(node)
            # Wrap the recursive call with semaphore to control concurrency
            async_tasks.append(
                _dfs_with_semaphore(
                    task["awNumber"], node["description"], vrm, tenant, 
                    session, semaphore, batch_size
                )
            )
    
    # 5. Execute all child fetches in parallel (controlled by semaphore)
    if async_tasks:
        results = await asyncio.gather(*async_tasks, return_exceptions=True)
        
        # 6. Assign results back to the corresponding nodes
        for node, child_result in zip(nodes_with_tasks, results):
            # Handle exceptions gracefully
            if isinstance(child_result, Exception):
                logger.error(f"Error fetching children for {node['awNumber']}: {child_result}")
                node["childTasks"] = []
            else:
                node["childTasks"] = child_result
        
    # 7. Return the list of children for the current node_id
    return structured_children


async def _dfs_with_semaphore(
    node_id: str, 
    path: str, 
    vrm: str, 
    tenant: str, 
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    batch_size: int
) -> List[Dict[str, Any]]:
    """
    Wrapper for _dfs_async that uses a semaphore to limit concurrency.
    
    Args:
        node_id: The ID of the node whose direct children are to be fetched.
        path: The path taken to get to the current node.
        vrm: The VRM parameter for the API call.
        tenant: Tenant identifier
        session: Aiohttp session for connection pooling.
        semaphore: Semaphore to control concurrency
        batch_size: Maximum number of concurrent child fetches

    Returns:
        A list of dictionaries, where each dictionary is a child node with its full subtree.
    """
    async with semaphore:
        return await _dfs_async(node_id, path, vrm, tenant, session, semaphore, batch_size)

def extract_tasks_dfs(repair_tree_json):
    """
    Performs a Depth-First Search on the repair tree structure to extract all
    task AW numbers and descriptions at the leaf nodes.

    Args:
        repair_tree_json: A JSON string or list of dictionaries representing the repair tree.

    Returns:
        A list of dictionaries, where each dictionary contains 'awNumber' and 'description'
        for a task.
    """
    if isinstance(repair_tree_json, str):
        data = json.loads(repair_tree_json)
    else:
        data = repair_tree_json

    all_tasks = []

    def dfs(nodes):
        print(f"nodes: {type(nodes)}")
        for node in nodes:
            print(f"node: {node}")
            # Add the current node's task to the list
            if not node.get('childTasks'):
              all_tasks.append({
                  'awNumber': node.get('awNumber'),
                  'description': node.get('description')
              })

            # Recursively call DFS for child tasks if they exist
            if 'childTasks' in node and node['childTasks']:
                dfs(node['childTasks'])

    # The top level of your JSON is a list of root nodes
    dfs(data)

    return all_tasks
    


# --- API Endpoints ---


@app.post("/haynes-pro")
def haynes_pro(job_data: HaynesProJobData):
    if "full service" in job_data.workItems[0].title.lower():
        results_list = []
        service_systems_response = requests.get(f"{DOMAIN}/api/v1/RepairTree/{job_data.vrm}/services",headers=GLOBAL_HEADERS)
        log_haynes_pro_request(job_data.tenant, "Repair Tree Service Systems", job_data.vrm, f"{DOMAIN}/api/v1/", service_systems_response.url, datetime.now().isoformat())
        service_systems = service_systems_response.json()
        print(f"service systems: {service_systems}")
        
        chosen_service = gen_model.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"We are looking to do a time/mileage maintenance service for this vehicle. It uses {job_data.fuel} fuel and was manufactured in {job_data.manufacture_date}. Given the following service systems: {service_systems}, return the most appropriate service system. Return only the id and name of the service system in a json format.",
        )
        print(chosen_service.text)
        log_haynes_pro_request(job_data.tenant, "Gemini Service System Selection", job_data.vrm, f"https://generativelanguage.googleapis.com/v1beta/", "https://generativelanguage.googleapis.com/v1beta/{model=models/*}:generateContent", datetime.now().isoformat())
        chosen_service_id = chosen_service.text.split("```json")[1].split("```")[0]
        chosen_service_json = json.loads(chosen_service_id)
        print(f"chosen service: {chosen_service_json}")
        
        
        maintenace_services_response = requests.get(f"{DOMAIN}/api/v1/RepairTree/{job_data.vrm}/services/{chosen_service_json['serviceId']} ",headers=GLOBAL_HEADERS)
        log_haynes_pro_request(job_data.tenant, "Repair Tree Maintenance Services", job_data.vrm, f"{DOMAIN}", maintenace_services_response.url, datetime.now().isoformat())
        maintenance_services = maintenace_services_response.json()
        maintenance_periods = {period["id"]:period["name"] for period in maintenance_services}
        print(f"maintenance services: {maintenance_services}")

        days_since_last_service = (datetime.now() - datetime.strptime(job_data.last_service_date, "%Y-%m-%d")).days
        
        chosen_maintenance_period = gen_model.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"given the following maintenance periods: {maintenance_periods}, and given the vehicle has {job_data.mileage} miles and its last service was {days_since_last_service} days ago, return the most appropriate maintenance period. Return only the id and name of the maintenance period in a json format.",
        )
        log_haynes_pro_request(job_data.tenant, "Gemini Maintenance Period Selection", job_data.vrm, f"https://generativelanguage.googleapis.com/v1beta/", "https://generativelanguage.googleapis.com/v1beta/{model=models/*}:generateContent", datetime.now().isoformat())
        print(chosen_maintenance_period.text)
        maintenance_period_json = chosen_maintenance_period.text.split("```json")[1].split("```")[0]
        chosen_maintenance_period_json = json.loads(maintenance_period_json)
        period_name = chosen_maintenance_period_json['name']
        print(f"maintenance period id: {chosen_maintenance_period_json}")
        
        maintenance_tasks_response = requests.get(f"{DOMAIN}/api/v1/RepairTree/{job_data.vrm}/services/{chosen_service_json['serviceId']}/{chosen_maintenance_period_json['id']}",headers=GLOBAL_HEADERS)
        log_haynes_pro_request(job_data.tenant, "Repair Tree Maintenance Tasks", job_data.vrm, f"{DOMAIN}", maintenance_tasks_response.url, datetime.now().isoformat())
        maintenance_tasks = maintenance_tasks_response.json()
        print(f"maintenance tasks: {maintenance_tasks}")
        maintenance_tasks = check_maintenance_period(maintenance_tasks, days_since_last_service, int(job_data.mileage))
        #print(f"maintenance tasks: {maintenance_tasks}")
        results_list.append({"system_id": chosen_service_json['serviceId'], "period_id": chosen_maintenance_period_json['id'], "maintenance_tasks": maintenance_tasks, "period_name": chosen_maintenance_period_json['name']})
        return {
        "results": results_list,
        "tree_structure": {},
        "matched_work_items": {}
    }
    else:
        print("repair repair service")
        try:
            global REPAIR_TASKS
            global REPAIR_DESCRIPTIONS
            global bm25
            global annoy_index
            global full_repair_tree
            
            results_list = []
            
            # Now search for work items
            for work_item in job_data.workItems:
                category_match = search_bm25(work_item.title, bm25, top_k=100)
                semantic_match = search_annoy_index(work_item.title, annoy_index, model, top_k=5)
                #best_match = find_best_match(work_item.title, REPAIR_TASKS, text_key="description")
                for match in semantic_match:
                    aw_number = match["awNumber"]
                    
                    # get repair details
                    repair_detail_response = requests.get(f"{DOMAIN}/api/v1/RepairTree/{job_data.vrm}/Task/{aw_number}", headers=GLOBAL_HEADERS)
                    log_haynes_pro_request(job_data.tenant, "Repair Tree Task Details", job_data.vrm, f"{DOMAIN}", repair_detail_response.url, datetime.now().isoformat())
                    repair_detail = repair_detail_response.json()
                    
                    print(f"repair detail: {repair_detail}")
                
                    results_list.append(repair_detail)
        except Exception as e:
            print(e)
            print(traceback.format_exc())
            return {"title":"error"}
    return {
        "results": results_list,
        "tree_structure": {},
        "matched_work_items": results_list
    }
    
@app.post("/get-parts-quotes")
def get_parts_quotes(job_data: PartsQuoteJobData):
    suppliers_data = [supplier.model_dump() for supplier in job_data.suppliers]
    if PARTS_SEARCH_AVAILABLE == "true":
        parts_search_url = f"{DOMAIN}/api/v1/findparts/searchbygenart"
        
        
        payload = {
            "Vrm": job_data.vrm,
            "Genart": job_data.genart,
            "Suppliers": suppliers_data
        }
        parts_search_response = requests.post(parts_search_url, headers=GLOBAL_HEADERS, json=payload)
        log_haynes_pro_request(job_data.tenant, "Find Parts by Genart", job_data.vrm, f"{DOMAIN}", parts_search_response.url, datetime.now().isoformat())
        return parts_search_response.json()
    else:
        with open("parts_quotes.json", "r") as f:
            parts_quotes = json.load(f)
            
        with open("sample_quotes_response.json", "r") as f:
            sample_quotes_response = json.load(f)
            
        parts_quotes_response = gen_model.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"We need to generate some dummy parts quotes for the following vehicle: {job_data.vrm}. The supplier ids are {suppliers_data}. Use the following image urls and brands for the parts. {parts_quotes[str(job_data.genart)]} Return the parts quotes in a json format. {sample_quotes_response}",
        )
        log_haynes_pro_request(job_data.tenant, "Gemini Parts Quotes Generation", job_data.vrm, f"https://generativelanguage.googleapis.com/v1beta/", "https://generativelanguage.googleapis.com/v1beta/{model=models/*}:generateContent", datetime.now().isoformat())
        print(parts_quotes_response.text)
        
        parts_quotes_response_json = json.loads(parts_quotes_response.text.split("```json")[1].split("```")[0])
        print(f"parts quotes response json: {parts_quotes_response_json}")
        
        return parts_quotes_response_json
 
def check_maintenance_period(maintenance_tasks: dict, days_since_last_service: int, mileage: int) -> dict:
    """
    Filter maintenance tasks based on time/mileage requirements in remarks.
    
    Rules:
    - If requirement is fully met: includeByDefault = True, keep task
    - If requirement is 70%+ met but not fully: includeByDefault = False, keep task
    - Otherwise: remove task
    """
    months_since_last_service = days_since_last_service / 30.0
    filtered_tasks = []
    
    for task in maintenance_tasks.get("optionalTasks", []):
        criteria = task.get("criteria", "").lower().replace(",", "")
        is_mandatory = task.get("isMandatory", False)
        
        # Check month requirements
        month_matches = re.findall(r'(\d+)\s*months?', criteria)
        if month_matches:
            required_months = int(month_matches[0])
            if months_since_last_service >= required_months:
                # Fully met requirement
                is_mandatory = True
            elif months_since_last_service >= (required_months * 0.7):
                # 70%+ met but not fully
                is_mandatory = False
        
        # Check mile requirements
        mile_matches = re.findall(r'(\d+)\s*miles?', criteria)
        if mile_matches:
            required_miles = int(mile_matches[0])
            print(f"required miles: {required_miles}")
            print(f"mileage: {mileage}")
            print(f"{type(mileage)},{type(required_miles)}")
            if mileage >= required_miles:
                # Fully met requirement
                is_mandatory = True
            elif mileage >= (required_miles * 0.7):
                # 70%+ met but not fully
                is_mandatory = False
        
        # If no time/mileage requirements found in remark, keep the task with default behavior
        if not month_matches and not mile_matches:
            is_mandatory = task.get("isMandatory", False)
        
        if is_mandatory:
            # Update the task with the calculated isMandatory value
            task_copy = task.copy()
            task_copy["isMandatory"] = is_mandatory
            filtered_tasks.append(task_copy)
        else:
            filtered_tasks.append(task)
    
    # Return the filtered maintenance tasks structure
    result = maintenance_tasks.copy()
    result["optionalTasks"] = filtered_tasks
    return result
    

    
@app.get("/")
def read_root():
    return {"message": "Welcome to the JobNPart Backend API"}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)



