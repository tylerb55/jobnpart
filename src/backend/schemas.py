from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal

    
class WorkItem(BaseModel):
    title: str
    invoice_description: str
    parts_numbers: List[str]
    
class SupplierDetails(BaseModel):
    supplierId: int 
    
class PartsQuoteJobData(BaseModel):
    tenant: str
    part_name: List[str]
    vrm: str
    genart: List[int]
    suppliers: List[SupplierDetails]
    
class CreateTreeJobData(BaseModel):
    vrm: str
    tenant: str
    
class RepairDetailsJobData(BaseModel):
    vrm: str
    awNumbers: List[str]
    tenant: str
    
  
class NodeSearchJobData(BaseModel):
    vrid: str
    target_repairtime_type_id: str
    type_category: str
    nodeId: str
    

class JobData(BaseModel):
    jobNumber: str
    engine: str
    make: str
    model: str
    vrm: str
    workItems: List[WorkItem]
    year: str
    tenant: str
    
class HaynesProJobData(BaseModel):
    vrm: str
    fuel: str
    manufacture_date: str
    workItems: List[WorkItem]
    tenant: str
    mileage: str
    last_service_date: str
    
    

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
    tenant: str
    vin: str
    
class PartsLink24JobData(BaseModel):
    tenant: str
    brand: str
    vin: str
    workItems: List[WorkItem]
    
    