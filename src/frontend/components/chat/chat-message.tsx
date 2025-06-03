import { cn } from "@/lib/utils"

interface ChatMessageProps {
  content: string
  sender: "system" | "user"
}

export function ChatMessage({ content, sender }: ChatMessageProps) {
  return (
    <div
      className={cn(
        "max-w-[80%] rounded-lg p-3",
        sender === "system" ? "bg-gray-100 text-gray-900 mr-auto" : "bg-blue-600 text-white ml-auto",
      )}
    >
      {content}
    </div>
  )
}

