import React from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { Button } from './button'

interface ErrorStateProps {
  title?: string
  message?: string
  onRetry?: () => void
}

export function ErrorState({
  title = "Something went wrong",
  message = "Failed to load security evaluation metrics. Please verify the backend connection.",
  onRetry
}: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-6 text-center rounded-xl border border-destructive/30 bg-destructive/5 my-4">
      <AlertTriangle className="w-8 h-8 text-destructive mb-2 animate-bounce" />
      <h4 className="text-base font-semibold text-foreground">{title}</h4>
      <p className="text-xs text-muted-foreground max-w-sm mt-1 mb-4">{message}</p>
      {onRetry && (
        <Button onClick={onRetry} variant="destructive" size="sm" className="gap-2">
          <RefreshCw className="w-3.5 h-3.5" />
          Retry Request
        </Button>
      )}
    </div>
  )
}
