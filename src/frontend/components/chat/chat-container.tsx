"use client"

import { useState, useRef, useEffect } from "react"
import { SendHorizontal } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ChatMessage } from "./chat-message"
import { ChatOptions } from "./chat-options"
import { PartCard } from "../parts/part-card"
import { CategorySelector } from "../parts/category-selector"
import { SearchingIndicator } from "./searching-indicator"

// Mock data for parts
const mockParts = [
  {
    partName: "Front Brake Pads",
    partNumber: "BP-1234-VW",
    price: 45.99,
    stock: "In Stock",
    source: "SES Part Factors",
    compatibility: "Compatible with your vehicle",
  },
  {
    partName: "Front Brake Discs (Pair)",
    partNumber: "BD-5678-VW",
    price: 89.99,
    stock: "In Stock",
    source: "SES Part Factors",
    compatibility: "Compatible with your vehicle",
  },
  {
    partName: "Brake Caliper Repair Kit",
    partNumber: "BC-9012-VW",
    price: 32.5,
    stock: "2-3 days",
    source: "SES Part Factors",
    compatibility: "Compatible with your vehicle",
  },
]

interface ChatContainerProps {
  job: {
    id: string
    vehicle: {
      make: string
      model: string
      year: string
    }
    repairCategory: string
    workItems: Array<{
      description: string
      category: string
    }>
    analyzedData?: {
      suggestedCategories: string[]
      potentialParts: Array<{
        partName: string
        partNumber: string
        category: string
      }>
      urgency: string
    }
  }
  addPartToJob: (part: any) => void
  updateRepairCategory: (category: string) => void
  initialPartNumber?: string | null
}

type MessageType =
  | { type: "text"; content: string; sender: "system" | "user" }
  | { type: "options"; options: Array<{ label: string; value: string }> }
  | { type: "part"; part: any }
  | { type: "parts"; parts: any[] }
  | { type: "categories" }
  | { type: "input"; placeholder: string }
  | { type: "searching"; query: string; source: string }

export function ChatContainer({ job, addPartToJob, updateRepairCategory, initialPartNumber }: ChatContainerProps) {
  const [messages, setMessages] = useState<MessageType[]>([])
  const [input, setInput] = useState("")
  const [awaitingInput, setAwaitingInput] = useState(false)
  const [isSearching, setIsSearching] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Initialize chat based on job data
  useEffect(() => {
    const initialMessages: MessageType[] = [
      {
        type: "text",
        content: `Hi! I can help you find parts for the ${job.vehicle.make} ${job.vehicle.model} ${job.vehicle.year}.`,
        sender: "system",
      },
    ]

    if (initialPartNumber) {
      initialMessages.push({
        type: "text",
        content: `I see you're looking for part number: ${initialPartNumber}.`,
        sender: "system",
      })
    }

    // Add work item information if available
    if (job.workItems && job.workItems.length > 0) {
      const workItemDescriptions = job.workItems.map((item, index) => `${index + 1}. ${item.description}`).join("\n")

      initialMessages.push({
        type: "text",
        content: `I see you're working on:\n${workItemDescriptions}`,
        sender: "system",
      })
    }

    // Add urgency information if available
    if (job.analyzedData?.urgency) {
      initialMessages.push({
        type: "text",
        content: `This job has ${job.analyzedData.urgency.toLowerCase()} urgency.`,
        sender: "system",
      })
    }

    // Add suggested parts if available
    if (job.analyzedData?.potentialParts && job.analyzedData.potentialParts.length > 0) {
      initialMessages.push({
        type: "text",
        content: "Based on your job description, you might need these parts:",
        sender: "system",
      })

      // Convert potential parts to part cards
      const suggestedParts = job.analyzedData.potentialParts.map((part) => ({
        partName: part.partName,
        partNumber: part.partNumber,
        price: Math.round(Math.random() * 100 + 20) + 0.99, // Random price for demo
        stock: "In Stock",
        source: "SES Part Factors",
        compatibility: "Compatible with your vehicle",
      }))

      initialMessages.push({
        type: "parts",
        parts: suggestedParts,
      })
    }

    // Add options for next steps
    initialMessages.push({
      type: "text",
      content: "How would you like to proceed?",
      sender: "system",
    })

    // If we have suggested categories, use them
    if (job.analyzedData?.suggestedCategories && job.analyzedData.suggestedCategories.length > 0) {
      const categoryOptions = job.analyzedData.suggestedCategories.map((category) => ({
        label: `Browse ${category} Parts`,
        value: `category_${category.toLowerCase()}`,
      }))

      initialMessages.push({
        type: "options",
        options: [
          ...categoryOptions,
          { label: "Enter Part Number", value: "part_number" },
          { label: "Describe Part Needed", value: "describe_part" },
          { label: "Browse All Categories", value: "browse_category" },
        ],
      })
    } else {
      // Default options
      initialMessages.push({
        type: "options",
        options: [
          { label: "Enter Part Number", value: "part_number" },
          { label: "Describe Part Needed", value: "describe_part" },
          { label: "Browse by Category", value: "browse_category" },
        ],
      })
    }

    setMessages(initialMessages)
  }, [job])

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const handleSendMessage = () => {
    if (!input.trim()) return

    // Add user message
    setMessages([...messages, { type: "text", content: input, sender: "user" }])

    // Process based on current state
    processUserInput(input)

    // Clear input
    setInput("")
  }

  const handleOptionSelect = (value: string) => {
    // Handle category selection from suggested categories
    if (value.startsWith("category_")) {
      const category = value.replace("category_", "")
      const formattedCategory = category.charAt(0).toUpperCase() + category.slice(1)
      updateRepairCategory(formattedCategory)

      setMessages([
        ...messages,
        {
          type: "text",
          content: `You selected: ${formattedCategory}. What specific part are you looking for in this category?`,
          sender: "system",
        },
        { type: "input", placeholder: `e.g., pads for ${formattedCategory}` },
      ])
      setAwaitingInput(true)
      return
    }

    switch (value) {
      case "part_number":
        setMessages([
          ...messages,
          { type: "text", content: "Please enter the Part Number:", sender: "system" },
          { type: "input", placeholder: "e.g., BP-1234-VW" },
        ])
        setAwaitingInput(true)
        break

      case "describe_part":
        setMessages([
          ...messages,
          {
            type: "text",
            content: "Okay, please describe the part you need (e.g., 'front brake pads', 'alternator').",
            sender: "system",
          },
          { type: "input", placeholder: "Describe the part..." },
        ])
        setAwaitingInput(true)
        break

      case "browse_category":
        setMessages([
          ...messages,
          { type: "text", content: "Let's narrow it down. Please select the repair category:", sender: "system" },
          { type: "categories" },
        ])
        break

      case "search_again":
        setMessages([
          ...messages,
          { type: "text", content: "What part are you looking for?", sender: "system" },
          { type: "input", placeholder: "Describe the part..." },
        ])
        setAwaitingInput(true)
        break

      case "check_technical":
        simulateE3TechnicalSearch()
        break

      case "check_oem":
        simulatePartlink24Search()
        break
    }
  }

  const handleCategorySelect = (category: string) => {
    // Update job repair category
    updateRepairCategory(category)

    setMessages([
      ...messages,
      {
        type: "text",
        content: `You selected: ${category}. What specific part are you looking for in this category?`,
        sender: "system",
      },
      { type: "input", placeholder: `e.g., pads for ${category}` },
    ])
    setAwaitingInput(true)
  }

  const processUserInput = (userInput: string) => {
    setAwaitingInput(false)

    // Simulate search
    setMessages((prev) => [...prev, { type: "searching", query: userInput, source: "SES database" }])

    setIsSearching(true)

    // Simulate API delay
    setTimeout(() => {
      setIsSearching(false)

      // Remove searching indicator
      setMessages((prev) => prev.filter((msg) => msg.type !== "searching"))

      // For demo purposes, always show results for "brake" related searches
      if (userInput.toLowerCase().includes("brake") || userInput.toLowerCase().includes("bp-")) {
        setMessages((prev) => [
          ...prev,
          {
            type: "text",
            content: `Found ${mockParts.length} potential matches for '${userInput}'.`,
            sender: "system",
          },
          { type: "parts", parts: mockParts },
        ])
      } else if (userInput.trim() !== "") {
        // No results
        setMessages((prev) => [
          ...prev,
          {
            type: "text",
            content: `Sorry, I couldn't find a direct match for '${userInput}'. Would you like to try:`,
            sender: "system",
          },
          {
            type: "options",
            options: [
              { label: "Search Again", value: "search_again" },
              { label: "Check Technical Data (E3Technical)", value: "check_technical" },
              { label: "Browse OEM Catalog (Partlink24)", value: "check_oem" },
            ],
          },
        ])
      }
    }, 2000)
  }

  const simulateE3TechnicalSearch = () => {
    setMessages((prev) => [...prev, { type: "searching", query: "Technical data", source: "E3Technical" }])

    setTimeout(() => {
      setMessages((prev) => [
        ...prev.filter((msg) => msg.type !== "searching"),
        {
          type: "text",
          content: "Fetching data from E3Technical... (Note: This action may incur a charge).",
          sender: "system",
        },
        {
          type: "text",
          content:
            "Technical data retrieved: Front brake pad thickness should be minimum 4mm. Recommended replacement: BP-1234-VW.",
          sender: "system",
        },
        { type: "part", part: mockParts[0] },
      ])
    }, 3000)
  }

  const simulatePartlink24Search = () => {
    setMessages((prev) => [...prev, { type: "searching", query: "OEM parts", source: "Partlink24" }])

    setTimeout(() => {
      setMessages((prev) => [
        ...prev.filter((msg) => msg.type !== "searching"),
        {
          type: "text",
          content: "Fetching data from Partlink24... (Note: This action may incur a charge).",
          sender: "system",
        },
        {
          type: "text",
          content: "Found OEM part information: Original VW Brake Pads (BP-1234-VW-OEM)",
          sender: "system",
        },
        {
          type: "part",
          part: {
            partName: "Original VW Brake Pads",
            partNumber: "BP-1234-VW-OEM",
            price: 69.99,
            stock: "Available to order",
            source: "Partlink24 (OEM)",
            compatibility: "Compatible with your vehicle",
          },
        },
      ])
    }, 3000)
  }

  const handleAddPart = (part: any) => {
    addPartToJob(part)

    setMessages((prev) => [
      ...prev,
      {
        type: "text",
        content: `Added ${part.partName} (${part.partNumber}) to Job ${job.id}.`,
        sender: "system",
      },
      {
        type: "text",
        content: "Is there anything else you need help with?",
        sender: "system",
      },
      {
        type: "options",
        options: [
          { label: "Find Another Part", value: "search_again" },
          { label: "Browse by Category", value: "browse_category" },
        ],
      },
    ])
  }

  return (
    <div className="flex flex-col h-[600px]">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, index) => {
          if (message.type === "text") {
            return <ChatMessage key={index} content={message.content} sender={message.sender} />
          } else if (message.type === "options") {
            return <ChatOptions key={index} options={message.options} onSelect={handleOptionSelect} />
          } else if (message.type === "part") {
            return <PartCard key={index} part={message.part} onAddToJob={handleAddPart} />
          } else if (message.type === "parts") {
            return (
              <div key={index} className="space-y-3">
                {message.parts.map((part, partIndex) => (
                  <PartCard
                    key={`${index}-${partIndex}`}
                    part={part}
                    onAddToJob={handleAddPart}
                    isRecommended={partIndex === 0}
                  />
                ))}
              </div>
            )
          } else if (message.type === "categories") {
            return <CategorySelector key={index} onSelect={handleCategorySelect} />
          } else if (message.type === "searching") {
            return <SearchingIndicator key={index} query={message.query} source={message.source} />
          }
          return null
        })}

        {/* Invisible element to scroll to */}
        <div ref={messagesEndRef} />
      </div>

      <div className="border-t p-4">
        <div className="flex gap-2">
          <Input
            placeholder={awaitingInput ? "Type here..." : "Ask about parts..."}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
            disabled={isSearching}
          />
          <Button onClick={handleSendMessage} disabled={isSearching || !input.trim()}>
            <SendHorizontal className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}
