"use client"

import { Button } from "@/components/ui/button"
import { Disc, FuelIcon as Engine, Battery, Filter, Wrench, Gauge, Lightbulb, Droplet } from "lucide-react"

interface CategorySelectorProps {
  onSelect: (category: string) => void
}

export function CategorySelector({ onSelect }: CategorySelectorProps) {
  const categories = [
    { name: "Brakes", icon: <Disc className="h-4 w-4" /> },
    { name: "Engine", icon: <Engine className="h-4 w-4" /> },
    { name: "Suspension", icon: <Wrench className="h-4 w-4" /> },
    { name: "Electrical", icon: <Battery className="h-4 w-4" /> },
    { name: "Filters", icon: <Filter className="h-4 w-4" /> },
    { name: "Instruments", icon: <Gauge className="h-4 w-4" /> },
    { name: "Lighting", icon: <Lightbulb className="h-4 w-4" /> },
    { name: "Fluids", icon: <Droplet className="h-4 w-4" /> },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
      {categories.map((category) => (
        <Button
          key={category.name}
          variant="outline"
          className="flex flex-col h-auto py-3 gap-2"
          onClick={() => onSelect(category.name)}
        >
          {category.icon}
          <span>{category.name}</span>
        </Button>
      ))}
    </div>
  )
}

