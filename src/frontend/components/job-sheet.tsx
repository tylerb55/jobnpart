"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Trash2, Settings, X } from "lucide-react"
import { CalendarIcon } from "lucide-react"
import { format } from "date-fns"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { cn } from "@/lib/utils"
import { useRouter } from "next/navigation"
import { toast } from "sonner"
import type { PartsData, ChatPageData, WorkItem as ChatWorkItem, JobDetailsForChat } from "@/app/types"

interface WorkItem {
  id: string
  workType: string
  mechanic: string
  notes: string
  status: string
  partType: string
  invoiceDescription: string
  labourHours: number
  labourCost: number
  partsSales: number
  discount: number
  vat: number
  remainder: number
  salesValue: number
}

// Define type for callEndpoint payload
interface HaynesProPayload {
  vin: string;
  jobId: string;
  car: string;
  vrm: string;
  customer: string;
  timestamp: string;
  workItems: ChatWorkItem[];
}

export function JobSheet() {
  const router = useRouter()
  const [isSubmitting, setIsSubmitting] = useState(false)

  const [jobDetails, setJobDetails] = useState({
    jobId: "1",
    dueDate: undefined as Date | undefined,
    description: "",
    car: "",
    vrm: "",
    vin: "",
    customer: "",
    mileage: "",
    location: "",
    mechanic: "",
  })

  const [workItems, setWorkItems] = useState<WorkItem[]>([])

  const [newWorkItem, setNewWorkItem] = useState({
    workType: "Advisory",
    part: "",
    quickPrice: "",
    advisoryWork: "",
  })

  const [checkboxes, setCheckboxes] = useState({
    loyaltyScheme: false,
    trade: false,
    customerInvoices: false,
    quotes: false,
  })

  const [jobNotes, setJobNotes] = useState("all-advisories")

  const addWorkItem = () => {
    if (newWorkItem.advisoryWork) {
      const newItem: WorkItem = {
        id: Date.now().toString(),
        workType: newWorkItem.advisoryWork,
        mechanic: jobDetails.mechanic,
        notes: "",
        status: "New",
        partType: "PT",
        invoiceDescription: newWorkItem.advisoryWork,
        labourHours: 0,
        labourCost: Number.parseFloat(newWorkItem.quickPrice) || 0,
        partsSales: 0,
        discount: 0,
        vat: 0,
        remainder: 0,
        salesValue: Number.parseFloat(newWorkItem.quickPrice) || 0,
      }
      setWorkItems([...workItems, newItem])
      setNewWorkItem({ workType: "Advisory", part: "", quickPrice: "", advisoryWork: "" })
    }
  }

  const removeWorkItem = (id: string) => {
    setWorkItems(workItems.filter((item) => item.id !== id))
  }

  const updateWorkItem = <K extends keyof WorkItem>(id: string, field: K, value: WorkItem[K]) => {
    setWorkItems(workItems.map((item) => (item.id === id ? { ...item, [field]: value } : item)))
  }

  const calculateTotal = () => {
    return workItems.reduce((total, item) => total + item.salesValue, 0).toFixed(2)
  }

  const isVinEntered = () => {
    if (!jobDetails.vin) {
      return false
    }
    return true
  }

  const callEndpoint = async (endpoint: string, buttonName: string) => {
    if (!isVinEntered()) {
      toast.error("VIN Required", {
        description: `Please enter a VIN number first for ${buttonName}.`,
      })
      return
    }

    const simplifiedWorkItems: ChatWorkItem[] = workItems.map((item) => ({
      description: item.invoiceDescription || item.workType,
      category: "",
    }))

    try {
      const payload: HaynesProPayload = {
        vin: jobDetails.vin,
        jobId: jobDetails.jobId,
        car: jobDetails.car,
        vrm: jobDetails.vrm,
        customer: jobDetails.customer,
        timestamp: new Date().toISOString(),
        workItems: simplifiedWorkItems,
      }

      const response = await fetch(`http://localhost:8000/${endpoint}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      })

      if (response.ok) {
        const data = await response.json()
        if (buttonName === "Haynes Pro") {
          const newWindow = window.open("", "_blank")
          if (newWindow) {
            newWindow.document.write("<pre>" + JSON.stringify(data, null, 2) + "</pre>")
            newWindow.document.close()
          } else {
            toast.error("Error", {
              description: "Could not open pop-up window. Please check your pop-up blocker settings.",
            })
          }
        } else {
          toast(`${buttonName} Response`,{
            description: JSON.stringify(data, null, 2),
          })
        }
      } else {
        toast.error(`${buttonName} Request Failed`, {
          description: `${response.status} ${response.statusText}`,
        })
      }
    } catch (error) {
      console.error(`Error calling ${endpoint}:`, error)
      toast.error(`Error Connecting to ${buttonName}`,{
        description: error instanceof Error ? error.message : "Unknown error",
      })
    }
  }

  const handlePartsCatalogueSubmit = async () => {
    if (!isVinEntered()) {
      toast.error("VIN Required", {
        description: "Please enter a VIN number first to proceed to Parts Catalogue.",
      })
      return
    }
    setIsSubmitting(true)

    const simplifiedWorkItems: ChatWorkItem[] = workItems.map((item) => ({
      description: item.invoiceDescription || item.workType,
      category: "",
    }))

    const analysisSubmissionData: JobDetailsForChat = {
      jobNumber: jobDetails.jobId,
      vin: jobDetails.vin,
      make: jobDetails.car,
      model: "",
      year: "",
      engine: "",
      workItems: simplifiedWorkItems,
    }

    try {
      const response = await fetch("http://localhost:8000/analyse-job", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(analysisSubmissionData),
      })

      if (!response.ok) {
        let errorBody = "Could not retrieve error details."
        try {
          errorBody = await response.text()
        } catch { // Removed '_'
          // ignore
        }
        console.error("Analysis API Error:", response.status, errorBody)
        throw new Error(`Failed to analyze job details (Status: ${response.status}). ${errorBody.substring(0, 100)}`)
      }

      const partsDataList: PartsData[] = await response.json()

      const jobDetailsForChatPage: JobDetailsForChat = {
        jobNumber: jobDetails.jobId,
        vin: jobDetails.vin,
        make: jobDetails.car,
        model: "",
        year: "",
        engine: "",
        workItems: simplifiedWorkItems,
      }

      const chatPageData: ChatPageData = {
        jobDetails: jobDetailsForChatPage,
        partsDataList: partsDataList,
      }

      try {
        sessionStorage.setItem("chatPageData", JSON.stringify(chatPageData))
      } catch (storageError) {
        console.error("Failed to save chatPageData to sessionStorage:", storageError)
        toast.error("Storage Error", {
          description: "Could not save job data locally. Please try again.",
        })
        setIsSubmitting(false)
        return
      }

      router.push(`/chat`)
    } catch (error) {
      console.error("Parts Catalogue submission error:", error)
      toast.error("Submission Error", {
        description: error instanceof Error ? error.message : "An unexpected error occurred.",
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-blue-600 text-white p-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 bg-red-500 transform rotate-45"></div>
          <h1 className="text-lg font-semibold">Technician / Invoice View</h1>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="bg-white text-blue-600 hover:bg-gray-100">
            OPEN NEW WINDOW
          </Button>
          <Button variant="ghost" size="sm" className="text-white hover:bg-blue-700">
            <X className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Work Item Detail Header */}
      <div className="bg-white border-b p-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Work Item Detail</h2>
        <div className="flex gap-2">
          <Badge variant="destructive">TECHNICIAN VIEW</Badge>
          <Badge variant="secondary">PRICING VIEW</Badge>
          <Button variant="ghost" size="sm">
            <Settings className="w-4 h-4" />
          </Button>
        </div>
      </div>

      <div className="flex gap-4 p-4">
        {/* Left Panel */}
        <Card className="w-64 bg-blue-600 text-white">
          <CardContent className="p-4 space-y-4">
            <Button className="w-full bg-blue-500 hover:bg-blue-400 text-white">Open Part Selector</Button>

            <div className="space-y-2">
              <Label className="text-white">Work Type</Label>
              <Select
                value={newWorkItem.workType}
                onValueChange={(value) => setNewWorkItem({ ...newWorkItem, workType: value })}
              >
                <SelectTrigger className="bg-white text-black">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Advisory">Advisory</SelectItem>
                  <SelectItem value="Repair">Repair</SelectItem>
                  <SelectItem value="Service">Service</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-white">Part</Label>
              <Input
                className="bg-white text-black"
                value={newWorkItem.part}
                onChange={(e) => setNewWorkItem({ ...newWorkItem, part: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label className="text-white">Quick Price</Label>
              <Input
                className="bg-white text-black"
                type="number"
                value={newWorkItem.quickPrice}
                onChange={(e) => setNewWorkItem({ ...newWorkItem, quickPrice: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label className="text-white">Advisory Work</Label>
              <Input
                className="bg-white text-black"
                value={newWorkItem.advisoryWork}
                onChange={(e) => setNewWorkItem({ ...newWorkItem, advisoryWork: e.target.value })}
              />
            </div>

            <Button onClick={addWorkItem} className="w-full bg-blue-500 hover:bg-blue-400 text-white">
              Add Work Item
            </Button>
          </CardContent>
        </Card>

        {/* Main Content */}
        <div className="flex-1 space-y-4">
          {/* Job Details */}
          <Card>
            <CardContent className="p-6">
              <div className="grid grid-cols-3 gap-6">
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>Job ID</Label>
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 rounded-full bg-black"></div>
                        <span className="font-semibold">{jobDetails.jobId}</span>
                      </div>
                    </div>
                    <div>
                      <Label>Due Date</Label>
                      <Popover>
                        <PopoverTrigger asChild>
                          <Button
                            variant="outline"
                            className={cn(
                              "w-full justify-start text-left font-normal",
                              !jobDetails.dueDate && "text-muted-foreground",
                            )}
                          >
                            <CalendarIcon className="mr-2 h-4 w-4" />
                            {jobDetails.dueDate ? format(jobDetails.dueDate, "PPP") : <span>Pick a date</span>}
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-auto p-0" align="start">
                          <Calendar
                            mode="single"
                            selected={jobDetails.dueDate}
                            onSelect={(date) => setJobDetails({ ...jobDetails, dueDate: date })}
                            initialFocus
                          />
                        </PopoverContent>
                      </Popover>
                    </div>
                  </div>

                  <div>
                    <Label>Description</Label>
                    <Textarea
                      value={jobDetails.description}
                      onChange={(e) => setJobDetails({ ...jobDetails, description: e.target.value })}
                      className="min-h-[60px]"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>Car</Label>
                      <Input
                        value={jobDetails.car}
                        onChange={(e) => setJobDetails({ ...jobDetails, car: e.target.value })}
                      />
                    </div>
                    <div>
                      <Label>VRM</Label>
                      <Input
                        value={jobDetails.vrm}
                        onChange={(e) => setJobDetails({ ...jobDetails, vrm: e.target.value })}
                      />
                    </div>
                    <div>
                      <Label className="flex items-center">
                        VIN <span className="text-red-500 ml-1">*</span>
                      </Label>
                      <Input
                        value={jobDetails.vin}
                        onChange={(e) => setJobDetails({ ...jobDetails, vin: e.target.value })}
                        className={!jobDetails.vin ? "border-red-300" : ""}
                        placeholder="Required for parts lookup"
                      />
                    </div>
                  </div>

                  <div>
                    <Label>Customer</Label>
                    <Input
                      value={jobDetails.customer}
                      onChange={(e) => setJobDetails({ ...jobDetails, customer: e.target.value })}
                    />
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center space-x-2">
                      <Checkbox
                        id="loyalty"
                        checked={checkboxes.loyaltyScheme}
                        onCheckedChange={(checked) =>
                          setCheckboxes({ ...checkboxes, loyaltyScheme: checked as boolean })
                        }
                      />
                      <Label htmlFor="loyalty">Loyalty Scheme</Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Checkbox
                        id="trade"
                        checked={checkboxes.trade}
                        onCheckedChange={(checked) => setCheckboxes({ ...checkboxes, trade: checked as boolean })}
                      />
                      <Label htmlFor="trade">Trade</Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Checkbox
                        id="invoices"
                        checked={checkboxes.customerInvoices}
                        onCheckedChange={(checked) =>
                          setCheckboxes({ ...checkboxes, customerInvoices: checked as boolean })
                        }
                      />
                      <Label htmlFor="invoices">Customer Invoices</Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Checkbox
                        id="quotes"
                        checked={checkboxes.quotes}
                        onCheckedChange={(checked) => setCheckboxes({ ...checkboxes, quotes: checked as boolean })}
                      />
                      <Label htmlFor="quotes">Quotes</Label>
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  <div>
                    <Label>Mileage</Label>
                    <Input
                      value={jobDetails.mileage}
                      onChange={(e) => setJobDetails({ ...jobDetails, mileage: e.target.value })}
                    />
                  </div>
                  <div>
                    <Label>Location</Label>
                    <Input
                      value={jobDetails.location}
                      onChange={(e) => setJobDetails({ ...jobDetails, location: e.target.value })}
                    />
                  </div>
                  <div>
                    <Label>Mechanic</Label>
                    <Input
                      value={jobDetails.mechanic}
                      onChange={(e) => setJobDetails({ ...jobDetails, mechanic: e.target.value })}
                    />
                  </div>
                </div>

                <div className="space-y-4">
                  <Button
                    onClick={handlePartsCatalogueSubmit}
                    className="w-full h-12 bg-yellow-400 hover:bg-yellow-500 text-black font-semibold flex justify-center items-center"
                    disabled={isSubmitting}
                  >
                    {isSubmitting ? "Analyzing..." : "Parts Catalogue"}
                  </Button>

                  <Button
                    onClick={() => callEndpoint("haynes-pro", "Haynes Pro")}
                    className="w-full h-12 bg-yellow-400 hover:bg-yellow-500 text-black font-semibold flex justify-center items-center"
                  >
                    Haynes Pro
                  </Button>

                  <Button
                    onClick={() => {
                      if (!isVinEntered()) {
                        toast.error("VIN Required", {
                          description: "Please enter a VIN number first to open partslink24.",
                        })
                        return
                      }
                      window.open("https://www.partslink24.com/partslink24/user/login.do", "_blank")
                    }}
                    className="w-full h-12 bg-yellow-400 hover:bg-yellow-500 text-black font-semibold flex justify-center items-center"
                  >
                    partslink24
                  </Button>
                </div>
              </div>

              <div className="flex gap-4 mt-6">
                <Button className="bg-orange-600 hover:bg-orange-700">CREATE INVOICE</Button>
                <Button className="bg-orange-600 hover:bg-orange-700">CREATE QUOTE</Button>
              </div>
            </CardContent>
          </Card>

          {/* Job Notes */}
          <Card>
            <CardContent className="p-4">
              <div className="space-y-4">
                <div>
                  <Label className="font-semibold">Job Notes</Label>
                  <div className="text-sm text-gray-600">Check Comments</div>
                </div>

                <RadioGroup value={jobNotes} onValueChange={setJobNotes} className="flex gap-6">
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="all-advisories" id="all" />
                    <Label htmlFor="all">All Advisories</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="dangerous-major" id="dangerous" />
                    <Label htmlFor="dangerous">Only Dangerous and Major</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="minor-advisory" id="minor" />
                    <Label htmlFor="minor">Only Minor And Advisory</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="none" id="none" />
                    <Label htmlFor="none">None</Label>
                  </div>
                </RadioGroup>
              </div>
            </CardContent>
          </Card>

          {/* Work Items Table */}
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b">
                    <tr className="text-xs">
                      <th className="text-left p-2">Work / Mechanic</th>
                      <th className="text-left p-2">Notes</th>
                      <th className="text-left p-2">Status</th>
                      <th className="text-left p-2">PT</th>
                      <th className="text-left p-2">Invoice Description</th>
                      <th className="text-left p-2">Labour Hours</th>
                      <th className="text-left p-2">Labour Cost (ex VAT)</th>
                      <th className="text-left p-2">Parts Sales (ex VAT)</th>
                      <th className="text-left p-2">Discount %</th>
                      <th className="text-left p-2">VAT</th>
                      <th className="text-left p-2">Remainder</th>
                      <th className="text-left p-2">Sales Value (ex VAT)</th>
                      <th className="text-left p-2">Sales Value (inc VAT)</th>
                      <th className="text-left p-2">Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {workItems.map((item) => (
                      <tr key={item.id} className="border-b hover:bg-gray-50">
                        <td className="p-2">
                          <div className="flex items-center gap-2">
                            <div className="w-4 h-4 bg-green-500 rounded"></div>
                            <div>
                              <div className="font-medium text-sm">{item.workType}</div>
                              <div className="text-xs text-gray-500">{item.mechanic}</div>
                            </div>
                          </div>
                        </td>
                        <td className="p-2">
                          <Input
                            className="w-20 h-8 text-xs"
                            value={item.notes}
                            onChange={(e) => updateWorkItem(item.id, "notes", e.target.value)}
                          />
                        </td>
                        <td className="p-2">
                          <Badge variant="secondary" className="text-xs">
                            {item.status}
                          </Badge>
                        </td>
                        <td className="p-2 text-xs">{item.partType}</td>
                        <td className="p-2">
                          <Input
                            className="w-32 h-8 text-xs"
                            value={item.invoiceDescription}
                            onChange={(e) => updateWorkItem(item.id, "invoiceDescription", e.target.value)}
                          />
                        </td>
                        <td className="p-2">
                          <Input
                            className="w-16 h-8 text-xs"
                            type="number"
                            value={item.labourHours}
                            onChange={(e) =>
                              updateWorkItem(item.id, "labourHours", Number.parseFloat(e.target.value) || 0)
                            }
                          />
                        </td>
                        <td className="p-2">
                          <Input
                            className="w-20 h-8 text-xs"
                            type="number"
                            value={item.labourCost}
                            onChange={(e) =>
                              updateWorkItem(item.id, "labourCost", Number.parseFloat(e.target.value) || 0)
                            }
                          />
                        </td>
                        <td className="p-2">
                          <Input
                            className="w-20 h-8 text-xs"
                            type="number"
                            value={item.partsSales}
                            onChange={(e) =>
                              updateWorkItem(item.id, "partsSales", Number.parseFloat(e.target.value) || 0)
                            }
                          />
                        </td>
                        <td className="p-2">
                          <Input
                            className="w-16 h-8 text-xs"
                            type="number"
                            value={item.discount}
                            onChange={(e) =>
                              updateWorkItem(item.id, "discount", Number.parseFloat(e.target.value) || 0)
                            }
                          />
                        </td>
                        <td className="p-2">
                          <Checkbox />
                        </td>
                        <td className="p-2">
                          <div className="w-4 h-4 bg-blue-500 rounded"></div>
                        </td>
                        <td className="p-2 text-xs font-medium">£{item.salesValue.toFixed(2)}</td>
                        <td className="p-2 text-xs font-medium">£{(item.salesValue * 1.2).toFixed(2)}</td>
                        <td className="p-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => removeWorkItem(item.id)}
                            className="h-6 w-6 p-0 text-red-500 hover:text-red-700"
                          >
                            <Trash2 className="w-3 h-3" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Incomplete Advisories */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Incomplete Advisories</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b">
                    <tr className="text-xs">
                      <th className="text-left p-2">Original Job Date</th>
                      <th className="text-left p-2">Work Item</th>
                      <th className="text-left p-2">Due Date</th>
                      <th className="text-left p-2">Status</th>
                      <th className="text-left p-2">Work Item Value</th>
                      <th className="text-left p-2">Related Job</th>
                      <th className="text-left p-2">Add to Job</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td colSpan={7} className="p-4 text-center text-gray-500 text-sm">
                        No incomplete advisories
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Footer with Totals */}
          <div className="bg-blue-600 text-white p-4 flex justify-between items-center">
            <div className="flex gap-4">
              <Button variant="outline" className="bg-white text-blue-600 hover:bg-gray-100">
                RELOAD
              </Button>
              <Button variant="outline" className="bg-white text-blue-600 hover:bg-gray-100">
                SHOW ALL FIELDS
              </Button>
            </div>
            <div className="flex gap-8 items-center">
              <div className="text-right">
                <div className="text-sm">Grand Total</div>
                <div className="text-sm">(ex VAT)</div>
                <div className="text-xl font-bold">£{calculateTotal()}</div>
              </div>
              <div className="text-right">
                <div className="text-sm">Grand Total</div>
                <div className="text-sm">(inc VAT)</div>
                <div className="text-xl font-bold">£{(Number.parseFloat(calculateTotal()) * 1.2).toFixed(2)}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
