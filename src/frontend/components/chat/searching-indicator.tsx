import { Loader2 } from "lucide-react"

interface SearchingIndicatorProps {
  query: string
  source: string
}

export function SearchingIndicator({ query, source }: SearchingIndicatorProps) {
  return (
    <div className="flex items-center gap-2 text-sm text-gray-500">
      <Loader2 className="h-4 w-4 animate-spin" />
      <span>
        Searching {source} for "{query}"...
      </span>
    </div>
  )
}

