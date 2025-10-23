# Background Job Queue System

## Overview

The repair tree building process is computationally expensive, especially when encoding descriptions with the sentence transformer model. To prevent timeouts and handle concurrent requests gracefully, we've implemented a background job queue system.

## Problem

The original `/create-tree-async` endpoint had issues:
- **Timeouts**: Large trees take 2-10+ minutes to build
- **Resource Exhaustion**: Multiple concurrent requests overwhelm CPU/memory
- **No Progress Tracking**: Users don't know if the process is working
- **Blocking**: API is unresponsive during heavy processing

## Solution

We now offer **three approaches**, from simplest to most robust:

---

## Approach 1: Simple Semaphore (Already Implemented)

The original `/create-tree-async` endpoint now uses a semaphore to limit concurrent builds.

### How it works:
- Only 1 tree building operation runs at a time
- Other requests wait in queue
- Still blocks the requesting client

### Configuration:
```python
TREE_BUILD_SEMAPHORE = asyncio.Semaphore(1)  # Max concurrent builds
```

### Usage:
```bash
curl -X POST http://localhost:8000/create-tree-async \
  -H "Content-Type: application/json" \
  -d '{"vrm": "LX14GZK", "tenant": "my-tenant"}'
```

### Pros:
- Simple implementation
- No changes needed to existing clients
- Prevents resource exhaustion

### Cons:
- Still can timeout on slow connections
- No progress visibility
- Blocks until completion

---

## Approach 2: Job Queue System (RECOMMENDED)

New endpoints that immediately return a job ID and allow polling for status.

### New Endpoints:

#### 1. Submit Job: `POST /jobs/create-tree`
Submit a tree build job and get a job ID immediately.

**Request:**
```bash
curl -X POST http://localhost:8000/jobs/create-tree \
  -H "Content-Type: application/json" \
  -d '{"vrm": "LX14GZK", "tenant": "my-tenant"}'
```

**Response:**
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "pending",
  "message": "Job submitted successfully. Use /jobs/status/{job_id} to check progress.",
  "status_url": "/jobs/status/123e4567-e89b-12d3-a456-426614174000",
  "result_url": "/jobs/result/123e4567-e89b-12d3-a456-426614174000"
}
```

#### 2. Check Status: `GET /jobs/status/{job_id}`
Check the current status and progress of a job.

**Request:**
```bash
curl http://localhost:8000/jobs/status/123e4567-e89b-12d3-a456-426614174000
```

**Response (In Progress):**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "vrm": "LX14GZK",
  "tenant": "my-tenant",
  "status": "in_progress",
  "created_at": "2025-10-21T12:00:00",
  "started_at": "2025-10-21T12:00:05",
  "completed_at": null,
  "progress": "Building search indexes for 1247 tasks... (this may take several minutes)",
  "error": null
}
```

**Response (Completed):**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "vrm": "LX14GZK",
  "status": "completed",
  "created_at": "2025-10-21T12:00:00",
  "started_at": "2025-10-21T12:00:05",
  "completed_at": "2025-10-21T12:08:32",
  "progress": "Completed successfully"
}
```

#### 3. Get Result: `GET /jobs/result/{job_id}`
Retrieve the complete repair tree once job is completed.

**Request:**
```bash
curl http://localhost:8000/jobs/result/123e4567-e89b-12d3-a456-426614174000
```

**Response:**
```json
{
  "awNumber": "root",
  "description": "Root Node",
  "parentNodeId": null,
  "childTasks": [...]
}
```

### Client Implementation Example:

#### Python Client:
```python
import requests
import time

def build_tree_with_polling(vrm: str, tenant: str, api_url: str = "http://localhost:8000"):
    # Submit job
    response = requests.post(
        f"{api_url}/jobs/create-tree",
        json={"vrm": vrm, "tenant": tenant}
    )
    job_id = response.json()["job_id"]
    print(f"Job submitted: {job_id}")
    
    # Poll for completion
    while True:
        status_response = requests.get(f"{api_url}/jobs/status/{job_id}")
        status_data = status_response.json()
        
        status = status_data["status"]
        progress = status_data.get("progress", "")
        
        print(f"Status: {status} - {progress}")
        
        if status == "completed":
            # Get result
            result_response = requests.get(f"{api_url}/jobs/result/{job_id}")
            return result_response.json()
        
        elif status == "failed":
            raise Exception(f"Job failed: {status_data.get('error')}")
        
        # Wait before next poll
        time.sleep(5)

# Usage
tree = build_tree_with_polling("LX14GZK", "my-tenant")
print(f"Tree built successfully with {len(tree['childTasks'])} root tasks")
```

#### JavaScript/TypeScript Client:
```typescript
async function buildTreeWithPolling(
  vrm: string, 
  tenant: string,
  apiUrl: string = "http://localhost:8000"
): Promise<any> {
  // Submit job
  const submitResponse = await fetch(`${apiUrl}/jobs/create-tree`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ vrm, tenant })
  });
  
  const { job_id } = await submitResponse.json();
  console.log(`Job submitted: ${job_id}`);
  
  // Poll for completion
  while (true) {
    const statusResponse = await fetch(`${apiUrl}/jobs/status/${job_id}`);
    const statusData = await statusResponse.json();
    
    console.log(`Status: ${statusData.status} - ${statusData.progress || ''}`);
    
    if (statusData.status === 'completed') {
      // Get result
      const resultResponse = await fetch(`${apiUrl}/jobs/result/${job_id}`);
      return await resultResponse.json();
    }
    
    if (statusData.status === 'failed') {
      throw new Error(`Job failed: ${statusData.error}`);
    }
    
    // Wait before next poll
    await new Promise(resolve => setTimeout(resolve, 5000));
  }
}

// Usage
const tree = await buildTreeWithPolling('LX14GZK', 'my-tenant');
console.log(`Tree built with ${tree.childTasks.length} root tasks`);
```

### Pros:
- No timeouts (returns immediately)
- Progress tracking
- Better user experience
- Handles concurrent requests gracefully
- Can be implemented without external dependencies

### Cons:
- Requires client-side polling logic
- Jobs stored in memory (lost on restart)
- Single server only (not distributed)

---

## Approach 3: Production-Grade with Celery + Redis

For true production scale, use a distributed task queue.

### Architecture:
```
┌──────────┐     ┌──────────┐     ┌───────┐     ┌─────────┐
│  Client  │────▶│ FastAPI  │────▶│ Redis │◀────│ Celery  │
└──────────┘     │  (API)   │     │(Queue)│     │ Worker  │
                 └──────────┘     └───────┘     └─────────┘
                      │                               │
                      │                               │
                      ▼                               ▼
                 ┌──────────┐                    ┌──────────┐
                 │ Supabase │                    │  Model   │
                 │ (Storage)│                    │ (e5-base)│
                 └──────────┘                    └──────────┘
```

### Installation:

1. **Install dependencies:**
```bash
pip install celery redis
```

2. **Update requirements.txt:**
```txt
celery==5.3.4
redis==5.0.1
```

3. **Start Redis:**
```bash
# Using Docker
docker run -d -p 6379:6379 redis:alpine

# Or install locally
# Ubuntu: sudo apt-get install redis-server
# Mac: brew install redis
```

### Implementation:

**Create `celery_app.py`:**
```python
from celery import Celery
import os

# Configure Celery
celery_app = Celery(
    'repair_tree_tasks',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0')
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3000,  # 50 minutes soft limit
)
```

**Create `celery_tasks.py`:**
```python
from celery_app import celery_app
from app import (
    download_from_supabase, 
    _build_search_indexes,
    _save_repair_tree_artifacts,
    extract_tasks_dfs
)
import aiohttp
import asyncio

@celery_app.task(bind=True)
def build_tree_task(self, vrm: str, tenant: str):
    """
    Celery task to build repair tree in background.
    """
    try:
        self.update_state(state='PROGRESS', meta={'progress': 'Starting...'})
        
        # Try cache first
        try:
            tree, annoy, bm25 = download_from_supabase(vrm)
            if tree:
                return tree
        except:
            pass
        
        # Build from scratch
        self.update_state(state='PROGRESS', meta={'progress': 'Fetching from API...'})
        
        # Run async code in new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # ... (rest of build logic)
        
        return result
        
    except Exception as e:
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise
```

**Update `app.py`:**
```python
from celery_tasks import build_tree_task

@app.post("/jobs/create-tree-celery")
async def submit_tree_build_celery(data: CreateTreeJobData):
    """Submit job to Celery"""
    task = build_tree_task.delay(data.vrm, data.tenant)
    return {"task_id": task.id}

@app.get("/jobs/celery-status/{task_id}")
async def get_celery_status(task_id: str):
    """Get Celery task status"""
    task = build_tree_task.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": task.state,
        "progress": task.info.get('progress') if task.info else None,
        "result": task.result if task.state == 'SUCCESS' else None
    }
```

### Running:

**Terminal 1 - API Server:**
```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

**Terminal 2 - Celery Worker:**
```bash
celery -A celery_tasks worker --loglevel=info --concurrency=1
```

**Terminal 3 - Celery Flower (Monitoring):**
```bash
celery -A celery_tasks flower
# Access at http://localhost:5555
```

### Pros:
- True distributed task queue
- Persistent jobs (survive restarts)
- Can scale to multiple workers
- Built-in monitoring (Flower)
- Industry standard
- Can handle very long tasks

### Cons:
- Additional infrastructure (Redis)
- More complex setup
- Higher operational overhead
- May be overkill for small deployments

---

## Render Deployment Considerations

### For Approach 1 (Semaphore):
No changes needed. Works out of the box.

### For Approach 2 (Job Queue):
1. Deploy as-is (already implemented)
2. Note: Jobs lost on redeploy
3. Consider periodic cleanup in production:

```python
# In lifespan startup
async def cleanup_task():
    while True:
        await asyncio.sleep(3600)  # Every hour
        job_queue.cleanup_old_jobs(max_age_hours=24)

asyncio.create_task(cleanup_task())
```

### For Approach 3 (Celery):
1. Add Redis addon in Render
2. Set `REDIS_URL` environment variable
3. Create separate worker service:
   - **Type**: Background Worker
   - **Start Command**: `celery -A celery_tasks worker --loglevel=info --concurrency=1`
4. Ensure both API and worker use same Supabase credentials

---

## Performance Tips

1. **Increase Gunicorn timeout** (already done in `gunicorn_config.py`):
   ```python
   timeout = 300  # 5 minutes
   ```

2. **Optimize model loading**:
   - Load sentence transformer once on startup ✅ (already done)
   - Use GPU if available: `model = SentenceTransformer('intfloat/e5-base-v2', device='cuda')`

3. **Batch processing**:
   ```python
   # In _build_search_indexes
   vectors = model.encode(
       repair_descriptions,
       batch_size=64,  # Adjust based on memory
       show_progress_bar=True
   )
   ```

4. **Cache aggressively**:
   - All built trees are cached in Supabase ✅
   - Consider caching in Redis for faster access

5. **Resource limits in Render**:
   - Use at least **2GB RAM** for encoding
   - Consider **4GB** for larger trees
   - CPU-optimized instance recommended

---

## Monitoring

### Basic Logging (Current):
```python
logger.info(f"[Job {job_id}] Building indexes for {len(tasks)} tasks")
```

### Advanced Monitoring (Optional):
```python
# Add to requirements.txt
# sentry-sdk==1.40.0

import sentry_sdk
sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"))
```

---

## Summary

| Feature | Semaphore | Job Queue | Celery+Redis |
|---------|-----------|-----------|--------------|
| Timeout Prevention | ❌ | ✅ | ✅ |
| Progress Tracking | ❌ | ✅ | ✅ |
| Concurrent Requests | Limited | ✅ | ✅ |
| Setup Complexity | Low | Low | High |
| Infrastructure | None | None | Redis |
| Persistence | ❌ | ❌ | ✅ |
| Scalability | Low | Medium | High |
| **Recommended For** | Development | Production (small) | Production (large) |

## Recommendation

- **Development**: Use Approach 1 (semaphore) - already implemented
- **Small Production (<100 users)**: Use Approach 2 (job queue) - already implemented
- **Large Production (>100 users)**: Implement Approach 3 (Celery+Redis)

The **job queue system (Approach 2) is already implemented and ready to use**. Just update your client to use the new `/jobs/create-tree` endpoint instead of `/create-tree-async`.

