"use client"

import { Check, Info, ShoppingCart } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

interface PartCardProps {
  part: {
    partName: string
    partNumber: string
    price?: number
    stock?: string
    source: string
    compatibility?: string
  }
  onAddToJob: (part: PartCardProps['part']) => void
  isRecommended?: boolean
}

export function PartCard({ part, onAddToJob, isRecommended = false }: PartCardProps) {
  const { partName, partNumber, price, stock, source, compatibility } = part

  return (
    <Card className={isRecommended ? "border-green-500" : ""}>
      {isRecommended && (
        <div className="bg-green-500 text-white text-xs font-medium py-1 px-3 flex items-center gap-1">
          <Check className="h-3 w-3" />
          Recommended
        </div>
      )}

      <CardContent className="p-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <div className="font-medium">{partName}</div>
            <div className="text-sm text-gray-500">{partNumber}</div>

            <div className="flex items-center gap-2 mt-1">
              <Badge variant="outline" className="text-xs">
                {source}
              </Badge>

              {compatibility && (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Badge variant="secondary" className="text-xs flex items-center gap-1">
                        <Check className="h-3 w-3" />
                        Compatible
                      </Badge>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>{compatibility}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
            </div>
          </div>

          <div className="flex flex-col items-end">
            {price && <div className="font-bold">£{price.toFixed(2)}</div>}

            {stock && <div className="text-xs text-gray-500">{stock}</div>}
          </div>
        </div>
      </CardContent>

      <CardFooter className="p-3 pt-0 flex gap-2 justify-end border-t">
        <Button variant="outline" size="sm" className="text-xs">
          <Info className="h-3 w-3 mr-1" />
          Technical Data
        </Button>

        <Button size="sm" className="text-xs" onClick={() => onAddToJob(part)}>
          <ShoppingCart className="h-3 w-3 mr-1" />
          Add to Job
        </Button>
      </CardFooter>
    </Card>
  )
}

