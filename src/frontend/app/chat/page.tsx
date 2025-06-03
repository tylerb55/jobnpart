"use client"

import { useEffect, useState } from "react"
// Remove useSearchParams import if no longer needed for other params
// import { useSearchParams } from "next/navigation"
import { CarPartsChat } from "@/components/car-parts-chat"
import { Skeleton } from "@/components/ui/skeleton"
import Link from "next/link"
// Import the type for the data structure we expect
import { ChatPageData } from "@/app/types" // Adjust path if needed

export default function ChatPage() {
  // State to hold the different parts of the data
  const [initialJobData, setInitialJobData] = useState<any>(null) // Use specific type if JobDetails type is available
  const [initialPartsDataList, setInitialPartsDataList] = useState<any[] | null>(null) // Use PartsData[] type
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let parsedPageData: ChatPageData | null = null
    let errorMessage: string | null = null

    try {
      // 1. Try to get the item using the new key "chatPageData"
      const chatPageDataString = sessionStorage.getItem("chatPageData")
      console.log("Raw data from sessionStorage (chatPageData):", chatPageDataString) // Debug log

      if (chatPageDataString) {
        try {
          parsedPageData = JSON.parse(chatPageDataString) as ChatPageData
          console.log("Parsed chatPageData:", parsedPageData) // Debug log

          // Validate the structure (basic check)
          if (!parsedPageData || !parsedPageData.jobDetails || !parsedPageData.partsDataList) {
            console.error("Parsed data is missing expected structure:", parsedPageData)
            throw new Error("Retrieved job data has an invalid format.")
          }

          // 2. Remove the item after successful parsing
          // Comment this out temporarily if still debugging sessionStorage issues
          //sessionStorage.removeItem("chatPageData")

        } catch (parseError: any) {
          console.error("Error parsing chatPageData from sessionStorage:", parseError)
          errorMessage = `Failed to read job data. It might be corrupted. (${parseError.message})`
          parsedPageData = null // Ensure data is null if parsing fails
        }
      } else {
        console.warn("No chatPageData found in sessionStorage.")
        errorMessage = "Job data not found. Please start from the job form again."
      }
    } catch (storageError: any) {
      console.error("Error accessing sessionStorage:", storageError)
      errorMessage = `Could not access session storage. Please ensure it is enabled. (${storageError.message})`
    }

    // Set state based on the parsed data
    if (parsedPageData) {
      setInitialJobData(parsedPageData.jobDetails)
      setInitialPartsDataList(parsedPageData.partsDataList)
    } else {
      setInitialJobData(null)
      setInitialPartsDataList(null)
    }
    setError(errorMessage)
    setIsLoading(false)

  }, []) // Empty dependency array - run only once on mount

  // Loading state check
  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center p-4 md:p-24 bg-gray-50">
        <div className="w-full max-w-6xl">
          <Skeleton className="h-8 w-64 mb-6 mx-auto" />
          <Skeleton className="h-[600px] w-full rounded-lg" />
        </div>
      </div>
    )
  }

  // Check for errors or if essential data is missing
  if (error || !initialJobData) { // Check initialJobData specifically
    return (
      <div className="flex min-h-screen flex-col items-center justify-center p-4 md:p-24 bg-gray-50">
        <div className="w-full max-w-6xl text-center">
          <h1 className="text-3xl font-bold mb-4">Error Loading Job Data</h1>
          <p className="mb-6 text-red-600">
            {error || "Could not retrieve job details."}
          </p>
          <Link href="/" className="text-blue-600 hover:underline">
            Return to Job Form
          </Link>
        </div>
      </div>
    )
  }

  // Render CarPartsChat if loading is done, no errors, and data exists
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-4 md:p-24 bg-gray-50">
      <div className="w-full max-w-6xl">
        <h1 className="text-3xl font-bold mb-6 text-center">Car Parts Search</h1>
        {/* Pass both parts of the data down */}
        <CarPartsChat
          initialJobData={initialJobData}
          initialPartsDataList={initialPartsDataList} // Pass the list as a new prop
        />
      </div>
    </main>
  )
}
