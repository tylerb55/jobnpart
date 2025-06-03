import { Car, FuelIcon as Engine, FileText } from "lucide-react"

interface JobContextProps {
  job: {
    id: string
    vehicle: {
      vin: string
      make: string
      model: string
      year: string
      engine: string
    }
    repairCategory: string
  }
}

export function JobContext({ job }: JobContextProps) {
  const { id, vehicle, repairCategory } = job
  const { make, model, year, vin, engine } = vehicle

  return (
    <div className="bg-gray-50 p-4 border-b">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-gray-500" />
          <span className="text-sm font-medium">Job: {id}</span>
        </div>

        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          <div className="flex items-center gap-1">
            <Car className="h-4 w-4 text-gray-500" />
            <span className="font-medium">
              {make} {model} {year}
            </span>
          </div>

          <div className="flex items-center gap-1">
            <Engine className="h-4 w-4 text-gray-500" />
            <span>{engine}</span>
          </div>

          <div className="text-xs text-gray-500">VIN: {vin}</div>
        </div>

        {repairCategory && (
          <div className="bg-blue-100 text-blue-800 px-2 py-0.5 rounded text-xs font-medium">{repairCategory}</div>
        )}
      </div>
    </div>
  )
}

