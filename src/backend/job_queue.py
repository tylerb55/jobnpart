"""
Background Job Queue System for Repair Tree Building

This module implements a simple job queue system to handle expensive operations
like repair tree building without blocking the API.
"""

from typing import Dict, Optional, Any
from datetime import datetime
from enum import Enum
import uuid
import asyncio
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job status enumeration"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    """Job data structure"""
    id: str
    vrm: str
    tenant: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    progress: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert job to dictionary for API responses"""
        data = asdict(self)
        # Convert datetime objects to ISO format strings
        data['created_at'] = self.created_at.isoformat() if self.created_at else None
        data['started_at'] = self.started_at.isoformat() if self.started_at else None
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        # Don't include full result in status response (can be large)
        if 'result' in data and data['result'] and self.status != JobStatus.COMPLETED:
            data['result'] = None
        return data


class JobQueue:
    """
    In-memory job queue for managing background tasks.
    
    For production, consider using:
    - Redis + Celery for distributed task queue
    - PostgreSQL for persistent job storage
    - RabbitMQ for message queue
    """
    
    def __init__(self, max_concurrent_jobs: int = 1):
        """
        Initialize job queue.
        
        Args:
            max_concurrent_jobs: Maximum number of jobs that can run simultaneously
        """
        self.jobs: Dict[str, Job] = {}
        self.semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self.max_concurrent_jobs = max_concurrent_jobs
        logger.info(f"Job queue initialized with max_concurrent_jobs={max_concurrent_jobs}")
    
    def create_job(self, vrm: str, tenant: str) -> str:
        """
        Create a new job and return its ID.
        
        Args:
            vrm: Vehicle Registration Mark
            tenant: Tenant identifier
            
        Returns:
            Job ID (UUID)
        """
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            vrm=vrm,
            tenant=tenant,
            status=JobStatus.PENDING,
            created_at=datetime.now()
        )
        self.jobs[job_id] = job
        logger.info(f"Created job {job_id} for VRM: {vrm}")
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID"""
        return self.jobs.get(job_id)
    
    def update_job_status(
        self, 
        job_id: str, 
        status: JobStatus, 
        result: Optional[Any] = None,
        error: Optional[str] = None,
        progress: Optional[str] = None
    ):
        """Update job status and related fields"""
        job = self.jobs.get(job_id)
        if not job:
            logger.warning(f"Attempted to update non-existent job: {job_id}")
            return
        
        job.status = status
        
        if status == JobStatus.IN_PROGRESS and not job.started_at:
            job.started_at = datetime.now()
        
        if status in (JobStatus.COMPLETED, JobStatus.FAILED):
            job.completed_at = datetime.now()
        
        if result is not None:
            job.result = result
        
        if error is not None:
            job.error = error
            
        if progress is not None:
            job.progress = progress
        
        logger.info(f"Job {job_id} status updated to {status}")
    
    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """
        Remove jobs older than max_age_hours.
        Should be called periodically to prevent memory leaks.
        """
        now = datetime.now()
        jobs_to_remove = []
        
        for job_id, job in self.jobs.items():
            age_hours = (now - job.created_at).total_seconds() / 3600
            if age_hours > max_age_hours:
                jobs_to_remove.append(job_id)
        
        for job_id in jobs_to_remove:
            del self.jobs[job_id]
            logger.info(f"Cleaned up old job: {job_id}")
        
        if jobs_to_remove:
            logger.info(f"Cleaned up {len(jobs_to_remove)} old jobs")


# Global job queue instance
job_queue = JobQueue(max_concurrent_jobs=1)

