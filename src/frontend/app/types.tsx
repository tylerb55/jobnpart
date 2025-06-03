// src/types.ts or similar
export interface WorkItem {
    description: string;
    category: string;
  }
  
  // Combining JobData from schema and usage in component
  export interface Job {
    id: string; // Renamed from jobNumber for consistency in component state
    vehicle: {
      vin: string;
      make: string;
      model: string;
      year: string;
      engine: string;
    };
    repairCategory: string;
    workItems: WorkItem[];
  }
  
  export interface Part {
    id?: string;
    nameId?: string;
    name?: string;
    number?: string; // This seems to be the unique identifier used as 'partNumber'
    notice?: string;
    description?: string;
    positionNumber?: string;
    url?: string;
  }
  
  // Type for the parts list state in CarPartsChat
  export type JobPart = Part & { quantity: number };
  
  export interface PartGroup {
    name: string;
    number?: string;
    positionNumber?: string;
    description?: string;
    parts: Part[];
  }
  
  export interface Position {
    number: string;
    coordinates: number[]; // [x,y,h,w] x and y are the top left corner of the bounding box
  }
  
  // Renamed from 'Parts' to avoid naming conflicts
  export interface PartsData {
    img: string;
    imgDescription?: string;
    brand: string;
    partGroups: PartGroup[];
    positions?: Position[];
  }
  
  export interface ChatPageData {
    jobDetails: { // Contains the original form input for context
      jobNumber: string;
      engine: string;
      make: string;
      model: string;
      vin: string;
      workItems: WorkItem[];
      year: string;
    };
    partsDataList: PartsData[]; // The list returned from the backend
  }