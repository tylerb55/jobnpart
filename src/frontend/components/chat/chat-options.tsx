"use client"

import { Button } from "@/components/ui/button"

interface ChatOptionsProps {
  options: Array<{ label: string; value: string }>
  onSelect: (value: string) => void
}

export function ChatOptions({ options, onSelect }: ChatOptionsProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((option, index) => (
        <Button key={index} variant="outline" onClick={() => onSelect(option.value)}>
          {option.label}
        </Button>
      ))}
    </div>
  )
}

