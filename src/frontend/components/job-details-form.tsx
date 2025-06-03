"use client"

import type React from "react"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Car, FileText, Plus, Trash2, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Card } from "@/components/ui/card"
import { toast } from "sonner"
import { WorkItem, PartsData, ChatPageData } from "@/app/types"

export function JobDetailsForm() {
  const router = useRouter()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [jobDetails, setJobDetails] = useState({
    jobNumber: "",
    vin: "",
    make: "",
    model: "",
    year: "",
    engine: "",
  })
  const [workItems, setWorkItems] = useState<WorkItem[]>([{ description: "", category: "" }])
  const [errors, setErrors] = useState<Record<string, string>>({})

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target
    setJobDetails((prev) => ({ ...prev, [name]: value }))
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: "" }))
    }
  }

  const handleWorkItemChange = (index: number, e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target
    const updatedWorkItems = [...workItems]
    updatedWorkItems[index] = { ...updatedWorkItems[index], [name]: value }
    setWorkItems(updatedWorkItems)
    const errorKey = `workItem-${index}-${name}`
    if (errors[errorKey]) {
      setErrors((prev) => ({ ...prev, [errorKey]: "" }))
    }
  }

  const addWorkItem = () => {
    setWorkItems([...workItems, { description: "", category: "" }])
  }

  const removeWorkItem = (index: number) => {
    if (workItems.length > 1) {
      setWorkItems(workItems.filter((_, i) => i !== index))
      const newErrors = { ...errors }
      delete newErrors[`workItem-${index}-description`]
      delete newErrors[`workItem-${index}-category`]
      setErrors(newErrors)
    }
  }

  const validateForm = () => {
    const newErrors: Record<string, string> = {}
    if (!jobDetails.jobNumber.trim()) newErrors.jobNumber = "Job Number is required"
    if (!jobDetails.vin.trim()) newErrors.vin = "VIN is required"
    workItems.forEach((item, index) => {
      if (!item.description.trim()) newErrors[`workItem-${index}-description`] = `Description for item ${index + 1} is required`
    })
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validateForm()) {
      toast({
        title: "Validation Error",
        description: "Please fill in all required fields.",
        variant: "destructive",
      })
      return
    }
    setIsSubmitting(true)

    const validWorkItems = workItems.filter((item) => item.description.trim() !== "")
    if (validWorkItems.length === 0) {
      toast({
        title: "Validation Error",
        description: "Please add at least one valid work item description.",
        variant: "destructive",
      })
      setIsSubmitting(false)
      return
    }

    const submissionData = {
      ...jobDetails,
      workItems: validWorkItems,
    }

    try {
      const response = await fetch("http://localhost:8000/analyse-job", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(submissionData),
      })

      if (!response.ok) {
        let errorBody = "Could not retrieve error details."
        try {
          errorBody = await response.text()
        } catch (_) {}
        console.error("Analysis API Error:", response.status, errorBody)
        throw new Error(`Failed to analyze job details (Status: ${response.status}). ${errorBody.substring(0, 100)}`)
      }

      const partsDataList: PartsData[] = await response.json()
      console.log("Received partsDataList from backend:", partsDataList)

      const chatPageData: ChatPageData = {
        jobDetails: submissionData,
        partsDataList: partsDataList,
      }

      try {
        sessionStorage.setItem("chatPageData", JSON.stringify(chatPageData))
        console.log("Combined chatPageData saved to sessionStorage:", sessionStorage.getItem("chatPageData"))
      } catch (storageError) {
        console.error("Failed to save chatPageData to sessionStorage:", storageError)
        toast({
          title: "Error",
          description: "Could not save job data locally. Please try again.",
          variant: "destructive",
        })
        setIsSubmitting(false)
        return
      }

      router.push(`/chat`)

    } catch (error) {
      console.error("Form submission error:", error)
      toast({
        title: "Submission Error",
        description: error instanceof Error ? error.message : "An unexpected error occurred.",
        variant: "destructive",
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="jobNumber">Job Number *</Label>
            <Input
              id="jobNumber"
              name="jobNumber"
              placeholder="e.g., JOB-2023-05-12"
              value={jobDetails.jobNumber}
              onChange={handleInputChange}
              required
            />
            {errors.jobNumber && <p className="text-red-500 text-xs mt-1">{errors.jobNumber}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="vin">VIN Number *</Label>
            <Input
              id="vin"
              name="vin"
              placeholder="e.g., WVWZZZ1KZAM053865"
              value={jobDetails.vin}
              onChange={handleInputChange}
              required
            />
            {errors.vin && <p className="text-red-500 text-xs mt-1">{errors.vin}</p>}
          </div>
        </div>

        <div className="border-t pt-4">
          <h2 className="text-lg font-medium mb-3 flex items-center">
            <Car className="mr-2 h-5 w-5" />
            Vehicle Details
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="make">Make *</Label>
              <Input
                id="make"
                name="make"
                placeholder="e.g., Volkswagen"
                value={jobDetails.make}
                onChange={handleInputChange}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="model">Model *</Label>
              <Input
                id="model"
                name="model"
                placeholder="e.g., Golf"
                value={jobDetails.model}
                onChange={handleInputChange}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="year">Year *</Label>
              <Input
                id="year"
                name="year"
                placeholder="e.g., 2020"
                value={jobDetails.year}
                onChange={handleInputChange}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="engine">Engine</Label>
              <Input
                id="engine"
                name="engine"
                placeholder="e.g., 2.0 TDI"
                value={jobDetails.engine}
                onChange={handleInputChange}
              />
            </div>
          </div>
        </div>

        <div className="border-t pt-4">
          <h2 className="text-lg font-medium mb-3 flex items-center">
            <FileText className="mr-2 h-5 w-5" />
            Work Items
          </h2>

          <div className="space-y-3">
            {workItems.map((item, index) => (
              <Card key={index} className="p-4">
                <div className="flex justify-between items-center mb-2">
                  <h3 className="font-medium">Work Item {index + 1}</h3>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => removeWorkItem(index)}
                    disabled={workItems.length === 1}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>

                <div className="space-y-3">
                  <div>
                    <Label htmlFor={`workItem-${index}-description`} className="text-xs">Description *</Label>
                    <Textarea
                      id={`workItem-${index}-description`}
                      name="description"
                      placeholder="Describe the work needed..."
                      value={item.description}
                      onChange={(e) => handleWorkItemChange(index, e)}
                      required
                      rows={2}
                    />
                    {errors[`workItem-${index}-description`] && <p className="text-red-500 text-xs mt-1">{errors[`workItem-${index}-description`]}</p>}
                  </div>

                  <div>
                    <Label htmlFor={`workItem-${index}-category`} className="text-xs">Category</Label>
                    <Input
                      id={`workItem-${index}-category`}
                      name="category"
                      placeholder="e.g., Brakes, Engine, Electrical"
                      value={item.category}
                      onChange={(e) => handleWorkItemChange(index, e)}
                    />
                  </div>
                </div>
              </Card>
            ))}

            <Button type="button" variant="outline" className="w-full" onClick={addWorkItem}>
              Add Another Work Item
            </Button>
          </div>
        </div>
      </div>

      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? "Analyzing..." : "Submit and Continue to Parts Search"}
      </Button>
    </form>
  )
}
