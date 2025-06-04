import { JobSheet } from "@/components/job-sheet"

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-4 md:p-24 bg-gray-50">
      <div className="w-full">
        <h1 className="text-3xl font-bold mb-6 text-center">Vehicle Job Details</h1>
        <div className="bg-white p-6 rounded-lg shadow-lg border">
          <JobSheet />
        </div>
      </div>
    </main>
  )
}
