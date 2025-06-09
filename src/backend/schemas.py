from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal

    
class WorkItem(BaseModel):
    title: str
    invoice_description: str

class JobData(BaseModel):
    jobNumber: str
    engine: str
    make: str
    model: str
    vin: str
    workItems: List[WorkItem]
    year: str
    
class HaynesProJobData(BaseModel):
    vin: str
    workItems: List[WorkItem]
    

class Part(BaseModel):
    id: Optional[str] = None
    nameId: Optional[str] = None
    name: Optional[str] = None
    number: Optional[str] = None
    notice: Optional[str] = None
    description: Optional[str] = None
    positionNumber: Optional[str] = None
    url: Optional[str] = None   
    
class PartGroup(BaseModel):
    name: str
    number: Optional[str] = None
    positionNumber: Optional[str] = None
    description: Optional[str] = None
    parts: List[Part]    
    
class Position(BaseModel):
    number: str
    coordinates: List[int]
    
class Parts(BaseModel):
    img: str
    imgDescription: Optional[str] = None
    brand: str
    partGroups: List[PartGroup]
    positions: Optional[List[Position]] = None

class CalculateRepairtimeJobData(BaseModel):
    target_repairtime_type_id: str
    type_category: str
    repairTaskIds: List[str]
    car_type_id: str
    
class RepairInstructionsJobData(BaseModel):
    target_repairtime_type_id: str
    type_category: str
    repairTaskIds: List[str]
    