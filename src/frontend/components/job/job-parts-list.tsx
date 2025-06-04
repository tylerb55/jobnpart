"use client"

import { Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card } from "@/components/ui/card"
import { JobPart } from "@/app/types"

interface JobPartsListProps {
  parts: JobPart[]
  updateQuantity: (partNumber: string, quantity: number) => void
}

export function JobPartsList({ parts, updateQuantity }: JobPartsListProps) {
  if (parts.length === 0) {
    return (
      <div className="p-8 text-center text-gray-500">
        <p>No parts added to this job yet.</p>
        <p className="text-sm mt-2">Parts you add will appear here.</p>
      </div>
    )
  }

  const totalPrice = parts.reduce((sum, part) => {
    return sum + (part.price || 0) * part.quantity
  }, 0)

  return (
    <div className="p-4">
      <div className="space-y-3">
        {parts.map((part) => (
          <Card key={part.number} className="p-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <div className="font-medium">{part.name}</div>
                <div className="text-sm text-gray-500">
                  {part.number} • {part.source}
                </div>
              </div>

              <div className="flex items-center gap-2">
                {part.price && <div className="text-sm font-medium">£{(part.price * part.quantity).toFixed(2)}</div>}

                <div className="flex items-center">
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8 rounded-r-none"
                    onClick={() => updateQuantity(part.number, part.quantity - 1)}
                  >
                    -
                  </Button>
                  <Input
                    type="number"
                    value={part.quantity}
                    onChange={(e) => updateQuantity(part.number, Number.parseInt(e.target.value) || 0)}
                    className="h-8 w-12 rounded-none text-center [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  />
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8 rounded-l-none"
                    onClick={() => updateQuantity(part.number, part.quantity + 1)}
                  >
                    +
                  </Button>
                </div>

                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-gray-500 hover:text-red-500"
                  onClick={() => updateQuantity(part.number, 0)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {totalPrice > 0 && (
        <div className="mt-4 flex justify-between items-center border-t pt-3">
          <span className="font-medium">Total</span>
          <span className="font-bold">£{totalPrice.toFixed(2)}</span>
        </div>
      )}

      <div className="mt-6">
        <Button className="w-full">Place Order</Button>
      </div>
    </div>
  )
}

