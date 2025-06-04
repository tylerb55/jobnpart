"use client"

import { useState, useEffect } from "react"
import { ChatContainer } from "./chat/chat-container"
import { DiagramViewer } from "./chat/diagram-viewer"
import { JobContext } from "./job/job-context"
import { JobPartsList } from "./job/job-parts-list"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Job, JobPart, PartsData, Part, WorkItem } from "@/app/types"

interface CarPartsChatProps {
  initialJobData?: {
    jobNumber: string;
    engine: string;
    make: string;
    model: string;
    vin: string;
    workItems: WorkItem[];
    year: string;
    analyzedData?: {
        suggestedCategories: string[];
        potentialParts: Part[];
        urgency: string;
    };
  } | null;
  initialPartsDataList?: PartsData[] | null;
}

// Define view types
type ChatView = 'diagram' | 'chat';

const defaultJob: Job = {
  id: "JOB-DEFAULT-ID",
  vehicle: {
    vin: "",
    make: "",
    model: "",
    year: "",
    engine: "",
  },
  repairCategory: "",
  workItems: [],
  analyzedData: {
    suggestedCategories: [],
    potentialParts: [],
    urgency: "Normal",
  },
}

export function CarPartsChat({ initialJobData, initialPartsDataList }: CarPartsChatProps) {
  const [job, setJob] = useState<Job>(() => {
    if (initialJobData) {
      return {
        id: initialJobData.jobNumber || defaultJob.id,
        vehicle: {
          vin: initialJobData.vin || "",
          make: initialJobData.make || "",
          model: initialJobData.model || "",
          year: initialJobData.year || "",
          engine: initialJobData.engine || "",
        },
        repairCategory: initialJobData.workItems?.[0]?.category || "",
        workItems: initialJobData.workItems || [],
        analyzedData: initialJobData.analyzedData || defaultJob.analyzedData,
      }
    }
    return defaultJob
  })

  const [jobParts, setJobParts] = useState<JobPart[]>([])

  const [diagramToView, setDiagramToView] = useState<PartsData | null>(() => {
      if (initialPartsDataList && initialPartsDataList.length > 0) {
          console.log("Initializing diagramToView with first item from list:", initialPartsDataList[0]);
          return initialPartsDataList[0];
      }
      console.log("Initializing diagramToView as null (no initial list or list empty)");
      return null;
  });

  const [currentView, setCurrentView] = useState<ChatView>('chat');
  const [selectedPartNumber, setSelectedPartNumber] = useState<string | null>(null);

  // Placeholder for onConfirmSelection prop
  const handleConfirmPartSelection = (selectedPartIds: string[]) => {
    console.log("Confirmed selected part IDs:", selectedPartIds);
    // TODO: Implement logic to handle confirmed parts (e.g., add to job, etc.)
  };

  useEffect(() => {
    console.log("CarPartsChat Props Received:", { initialJobData, initialPartsDataList });

    if (initialJobData) {
      console.log("Setting job from initialJobData:", initialJobData);
      setJob({
        id: initialJobData.jobNumber || defaultJob.id,
        vehicle: {
          vin: initialJobData.vin || "",
          make: initialJobData.make || "",
          model: initialJobData.model || "",
          year: initialJobData.year || "",
          engine: initialJobData.engine || "",
        },
        repairCategory: initialJobData.workItems?.[0]?.category || "",
        workItems: initialJobData.workItems || [],
        analyzedData: initialJobData.analyzedData || defaultJob.analyzedData,
      })
    } else {
      console.log("Setting job to defaultJob");
      setJob(defaultJob)
      setJobParts([])
    }

    if (initialPartsDataList && initialPartsDataList.length > 0) {
        console.log("Setting diagramToView from initialPartsDataList:", initialPartsDataList[0]);
        setDiagramToView(initialPartsDataList[0]);
        setCurrentView('diagram');
        setSelectedPartNumber(null);
    } else {
        console.log("Setting diagramToView to null (prop changed to null/empty)");
        setDiagramToView(null);
        setCurrentView('chat');
    }
  }, [initialJobData, initialPartsDataList])

  const addPartToJob = (part: Part) => {
    if (!part.number) {
      console.error("Attempted to add part without a number:", part)
      return
    }
    const existingPartIndex = jobParts.findIndex((p) => p.number === part.number)

    if (existingPartIndex >= 0) {
      const updatedParts = [...jobParts]
      updatedParts[existingPartIndex].quantity += 1
      setJobParts(updatedParts)
    } else {
      setJobParts([...jobParts, { ...part, quantity: 1 }])
    }
  }

  const updatePartQuantity = (partNumber: string, quantity: number) => {
    if (quantity <= 0) {
      setJobParts(jobParts.filter((p) => p.number !== partNumber))
    } else {
      setJobParts(jobParts.map((p) => (p.number === partNumber ? { ...p, quantity } : p)))
    }
  }

  const updateRepairCategory = (category: string) => {
    setJob({ ...job, repairCategory: category })
  }

  const handleHotspotSelect = (positionNumber: string) => {
    console.log(`Hotspot selected: Position ${positionNumber}`);
    let foundPartNumber: string | null = null;

    if (diagramToView) {
      for (const group of diagramToView.partGroups) {
        const foundPart = group.parts.find(part => part.positionNumber === positionNumber);
        if (foundPart) {
          foundPartNumber = foundPart.number || null;
          console.log(`Found Part Number: ${foundPartNumber}`);
          break;
        }
      }
    }

    if (foundPartNumber) {
      setSelectedPartNumber(foundPartNumber);
      setCurrentView('chat');
    } else {
      console.warn(`Could not find part number for position ${positionNumber}`);
    }
  };

  return (
    <div className="border rounded-lg shadow-lg bg-white">
      <JobContext job={job} />

      <Tabs defaultValue="main" className="w-full">
        <TabsList className="grid grid-cols-2 w-full">
          <TabsTrigger value="main">
            {currentView === 'diagram' ? 'Diagram' : 'Chat'}
          </TabsTrigger>
          <TabsTrigger value="parts">Parts List ({jobParts.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="main" className="p-0">
          {currentView === 'diagram' ? (
            <DiagramViewer
              diagramData={diagramToView}
              onHotspotSelect={handleHotspotSelect}
              onConfirmSelection={handleConfirmPartSelection}
            />
          ) : (
            <ChatContainer
              job={job}
              addPartToJob={addPartToJob}
              updateRepairCategory={updateRepairCategory}
              initialPartNumber={selectedPartNumber}
            />
          )}
        </TabsContent>

        <TabsContent value="parts" className="p-0">
          <JobPartsList parts={jobParts} updateQuantity={updatePartQuantity} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
