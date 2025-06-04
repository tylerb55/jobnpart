"use client"

// Add useMemo for data processing
import { useState, useRef, useEffect, SyntheticEvent, useMemo } from "react";
import { PartsData, Part } from "@/app/types" // Make sure Part type is imported/defined
import Image from "next/image";

// ... imports ...

interface DiagramViewerProps {
  diagramData: PartsData | null
  onConfirmSelection: (selectedPartIds: string[]) => void
  onHotspotSelect: (positionNumber: string) => void;
}

interface CollapsibleSectionProps {
  title: string;
  children: React.ReactNode;
  isExpanded: boolean;
  onToggle: () => void;
  id?: string; // For scrolling
}

const CollapsibleSection: React.FC<CollapsibleSectionProps> = ({ title, children, isExpanded, onToggle, id }) => {
  return (
      <div id={id} className="border border-gray-200 rounded mb-2 bg-white shadow-sm">
          <button
              onClick={onToggle}
              className="w-full flex justify-between items-center p-3 text-left font-medium text-gray-700 hover:bg-gray-50 focus:outline-none"
              aria-expanded={isExpanded}
          >
              <span>Position: {title}</span>
              {/* Simple arrow indicator */}
              <span className={`transform transition-transform duration-200 ${isExpanded ? 'rotate-180' : 'rotate-0'}`}>▼</span>
          </button>
          {isExpanded && (
              <div className="p-3 border-t border-gray-200 bg-gray-50"> {/* Added subtle background for expanded content */}
                  {children}
              </div>
          )}
      </div>
  );
};

export function DiagramViewer({ diagramData, onConfirmSelection, onHotspotSelect }: DiagramViewerProps) {
  // ... state variables (renderedSize, originalSize, isLoadingOriginalSize, expandedPositions, selectedPartIds) ...
  const [renderedSize, setRenderedSize] = useState<{ width: number; height: number } | null>(null);
  const [originalSize, setOriginalSize] = useState<{ width: number; height: number } | null>(null);
  const [isLoadingOriginalSize, setIsLoadingOriginalSize] = useState(false);
  const imageRef = useRef<HTMLImageElement>(null);
  const legendContainerRef = useRef<HTMLDivElement>(null); // Ref for the legend container

  // State for interactive legend
  const [expandedPositions, setExpandedPositions] = useState<Record<string, boolean>>({});
  const [selectedPartIds, setSelectedPartIds] = useState<Set<string>>(new Set());


  // ... useMemo for partsByPosition ...
  const partsByPosition = useMemo(() => {
    const grouped: Record<string, Part[]> = {};
    if (!diagramData?.partGroups) return grouped;

    diagramData.partGroups.forEach(group => {
      group.parts?.forEach(part => {
        // Ensure part.positionNumber and part.number exist
        if (part.positionNumber && part.number) {
          if (!grouped[part.positionNumber]) {
            grouped[part.positionNumber] = [];
          }
          grouped[part.positionNumber].push(part);
        }
      });
    });
     // Sort keys (position numbers) naturally (e.g., 1, 1A, 2, 10)
     const sortedKeys = Object.keys(grouped).sort((a, b) =>
        a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' })
    );
    const sortedGrouped: Record<string, Part[]> = {};
    sortedKeys.forEach(key => {
        sortedGrouped[key] = grouped[key];
    });

    return sortedGrouped;
  }, [diagramData?.partGroups]);


  // ... useEffect for original size calculation ...
  useEffect(() => {
    // reset states when the image changes
    setRenderedSize(null);
    setOriginalSize(null);
    setIsLoadingOriginalSize(false);
    // Reset legend state as well
    setExpandedPositions({});
    setSelectedPartIds(new Set());


    if (diagramData?.img) {
        setIsLoadingOriginalSize(true);
        // Ensure URL has a protocol
        const imageUrl = diagramData.img.startsWith('//') ? `https:${diagramData.img}` : diagramData.img;
        const img = new window.Image(); // Use window.Image to avoid conflict with next/image

        img.onload = () => {
          console.log(`Original dimensions calculated: ${img.naturalWidth}x${img.naturalHeight}`);
          setOriginalSize({ width: img.naturalWidth, height: img.naturalHeight });
          setIsLoadingOriginalSize(false);
        };

        img.onerror = (error) => {
          console.error("Error loading image to get original dimensions:", error);
          setOriginalSize(null); // Indicate failure
          setIsLoadingOriginalSize(false);
        };

        img.src = imageUrl; // Start loading the image in memory
      }
    }, [diagramData?.img]);


  // ... handleImageLoad ...
  const handleImageLoad = (event: SyntheticEvent<HTMLImageElement, Event>) => {
    const img = event.currentTarget;
    console.log(`Displayed image loaded. Rendered size: ${img.offsetWidth}x${img.offsetHeight}`);
    setRenderedSize({ width: img.offsetWidth, height: img.offsetHeight });
  };


  // ... togglePositionExpansion ...
  const togglePositionExpansion = (positionNumber: string) => {
    setExpandedPositions(prev => ({
        ...prev,
        [positionNumber]: !prev[positionNumber]
    }));
  };

  // ... togglePartSelection ...
  const togglePartSelection = (partId: string) => {
    setSelectedPartIds(prev => {
        const newSelection = new Set(prev);
        if (newSelection.has(partId)) {
            newSelection.delete(partId);
        } else {
            newSelection.add(partId);
        }
        return newSelection;
    });
  };

  // ... handleHotspotClick ...
  const handleHotspotClick = (positionNumber: string) => {
    onHotspotSelect(positionNumber); // Call the prop
    // Expand the section
    if (!expandedPositions[positionNumber]) {
        togglePositionExpansion(positionNumber);
    }
    // Scroll to the section
    // Use a slight delay to ensure the element is rendered after state update
    setTimeout(() => {
        const element = document.getElementById(`legend-pos-${positionNumber}`);
        element?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 100); // 100ms delay, adjust if needed
  };

  // ... handleConfirmClick ...
  const handleConfirmClick = () => {
    onConfirmSelection(Array.from(selectedPartIds));
  };


  if (!diagramData) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500 p-4">
        <p>No parts diagram data available.</p>
      </div>
    )
  }

  const positions = diagramData.positions || [];
  // ... scale factor calculation ...
  let scaleX = 1;
  let scaleY = 1;
  let canRenderHotspots = false;

  if (originalSize && renderedSize) {
    if (originalSize.width > 0 && originalSize.height > 0) {
        scaleX = renderedSize.width / originalSize.width;
        scaleY = renderedSize.height / originalSize.height;
        canRenderHotspots = true; // Ready to render
    } else {
        console.warn("Original image dimensions are zero, cannot calculate scale.");
    }
  }

  // Ensure URL has a protocol for next/image
  const imageUrl = diagramData.img.startsWith('//') ? `https:${diagramData.img}` : diagramData.img;


  // Main container: flex column, full height
  return (
    <div className="flex flex-col h-full bg-gray-50">

      {/* Diagram Area: Takes up initial space, allows shrinking */}
      <div className="flex-shrink-0 p-4 border-b border-gray-200 bg-white relative">
          {/* Container for Image + Hotspots */}
          <div className="relative w-full max-w-full mx-auto aspect-video" style={{ maxHeight: '65vh' }}> {/* Adjust maxHeight as needed */}
            {imageUrl && originalSize ? (
                <Image
                  ref={imageRef}
                  src={imageUrl}
                  alt={diagramData.imgDescription || 'Parts Diagram'}
                  width={0} // Provide original width for layout hints
                  height={0} // Provide original height for layout hints
                  className="block" // Ensure image behaves like a block element
                  sizes="(max-width: 768px) 90vw, 50vw" // Adjust sizes
                  style={{ // Constrain image height within container
                    width: 'auto', // Let height drive width if constrained by height
                    height: 'auto', // Let width drive height if constrained by width
                    objectFit: 'contain',
                    display: 'block',
                    backgroundColor: !renderedSize ? '#f0f0f0' : 'transparent',
                  }}
                  priority
                  onLoad={handleImageLoad}
                />
            ) : (
                <p>Image not available.</p>
            )}

            {/* ... Loading indicator ... */}
            {isLoadingOriginalSize && (
                 <div className="absolute inset-0 flex items-center justify-center bg-gray-500 bg-opacity-50 z-20">
                     <p className="text-white font-semibold">Loading diagram dimensions...</p>
                 </div>
             )}

            {/* ... Hotspot rendering logic ... */}
            {canRenderHotspots && positions.map((pos) => {
              // Find the corresponding position data from the separate positions array
              const positionData = diagramData.positions?.find(p => p.number === pos.number);
              if (!positionData || !positionData.coordinates || positionData.coordinates.length < 4) {
                  console.warn("Skipping hotspot render due to missing/invalid coordinate data for:", pos.number);
                  return null;
              }
              const [x, y, w, h] = positionData.coordinates;

              if (typeof x !== 'number' || typeof y !== 'number' || typeof w !== 'number' || typeof h !== 'number') {
                console.warn("Skipping position due to invalid coordinates:", pos.number);
                return null;
              }

              // Apply scaling factors
              const scaledX = x * scaleX;
              const scaledY = y * scaleY;
              const scaledW = w * scaleX;
              const scaledH = h * scaleY;

              if (scaledW < 5 || scaledH < 5) return null; // Skip tiny hotspots

              return (
                <button
                  key={pos.number}
                  // Use the new handler for hotspot clicks
                  onClick={() => handleHotspotClick(pos.number)}
                  className="absolute z-10 border-2 border-gray-200 hover:border-gray-800 bg-gray-0 bg-opacity-10 flex items-center justify-center text-xs text-blue-700 hover:text-blue-900 transition-colors duration-150 ease-in-out focus:outline-none focus:ring-1 focus:ring-offset-1 focus:ring-blue-500 cursor-pointer"
                  style={{
                    left: `${scaledX}px`,
                    top: `${scaledY}px`,
                    width: `${scaledW}px`,
                    height: `${scaledH}px`,
                    // Ensure text is visible if needed, or remove if number display isn't desired on hotspot itself
                    // color: 'transparent', // Hide number text on hotspot if desired
                  }}
                  title={`Go to legend section for position ${pos.number}`}
                  aria-label={`Go to legend section for position ${pos.number}`}
                >
                 {/* Optionally display number on hotspot */}
                 {/* {pos.number} */}
                </button>
              );
            })}
          </div> {/* End of relative container for image and hotspots */}
      </div>

      {/* --- Interactive Legend Section (Scrollable) --- */}
      <div ref={legendContainerRef} className="flex-grow overflow-y-auto p-4 border-t border-gray-200">
        <h4 className="text-md font-semibold mb-3 text-gray-800 sticky top-0 bg-gray-50 py-2 z-10">
            Parts Legend
            {selectedPartIds.size > 0 && ` (${selectedPartIds.size} selected)`}
        </h4>

        {Object.keys(partsByPosition).length > 0 ? (
            Object.entries(partsByPosition).map(([positionNumber, partsList]) => (
                <CollapsibleSection
                    key={positionNumber}
                    id={`legend-pos-${positionNumber}`} // ID for scrolling
                    title={positionNumber}
                    isExpanded={!!expandedPositions[positionNumber]}
                    onToggle={() => togglePositionExpansion(positionNumber)}
                >
                    {partsList.map((part) => {
                        if (typeof part.number !== 'string') {
                            return null; 
                        }
                        const currentPartNumber = part.number; // Explicitly string here
                        const isSelected = selectedPartIds.has(currentPartNumber);
                        return (
                            <div key={currentPartNumber} className="py-2 px-1 mb-2 border-b border-gray-100 last:border-b-0 hover:bg-gray-50 rounded">
                                <div className="flex justify-between items-start gap-3">
                                    <div>
                                        <p className="font-medium text-sm text-gray-800">
                                            {part.name} {part.notice && <span className="text-gray-500 text-xs">({part.notice})</span>}
                                        </p>
                                        <p className="text-xs text-gray-600 mt-1">Part No: <span className="font-mono bg-gray-100 px-1 rounded">{currentPartNumber}</span></p>
                                        {part.description && (
                                            <p className="text-xs text-gray-500 mt-1 whitespace-pre-wrap">{part.description}</p>
                                        )}
                                    </div>
                                    <button
                                        onClick={() => togglePartSelection(currentPartNumber)}
                                        className={`py-1 px-3 text-xs rounded transition-colors ${
                                            isSelected
                                                ? 'bg-red-100 text-red-700 hover:bg-red-200'
                                                : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                                        }`}
                                        title={isSelected ? `Deselect part ${currentPartNumber}` : `Select part ${currentPartNumber}`}
                                    >
                                        {isSelected ? 'Deselect' : 'Select'}
                                    </button>
                                </div>
                            </div>
                        );
                    })}
                </CollapsibleSection>
            ))
        ) : (
            <p className="text-sm text-gray-500">No parts listed in legend.</p>
        )}
      </div>
      {/* --- End Legend Section --- */}

       {/* --- Confirm Button Area --- */}
       {selectedPartIds.size > 0 && (
            <div className="p-4 border-t border-gray-200 bg-white sticky bottom-0 z-10 flex-shrink-0">
                <button
                    onClick={handleConfirmClick}
                    className="w-full py-2 px-4 bg-green-600 text-white font-semibold rounded hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50"
                    disabled={selectedPartIds.size === 0}
                >
                    Confirm Selection ({selectedPartIds.size} Part{selectedPartIds.size > 1 ? 's' : ''})
                </button>
            </div>
        )}

    </div> // End of main container div
  )
}