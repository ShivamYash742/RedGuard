import React from 'react'
import { ShieldAlert, RefreshCw } from 'lucide-react'
import { Button } from './button'

interface EmptyStateProps {
  icon?: React.ElementType
  title: string
  description: string
  actionLabel?: string
  onAction?: () => void
}

export function EmptyState({
  icon: Icon = ShieldAlert,
  title,
  description,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center rounded-xl border border-border/50 bg-card/40 backdrop-blur-md my-6">
      <div className="p-4 rounded-full bg-muted/50 text-muted-foreground mb-4">
        <Icon className="w-8 h-8 text-primary" />
      </div>
      <h3 className="text-lg font-semibold text-foreground mb-1">{title}</h3>
      <p className="text-sm text-muted-foreground max-w-md mb-6">{description}</p>
      {actionLabel && onAction && (
        <Button onClick={onAction} variant="outline" className="gap-2">
          <RefreshCw className="w-4 h-4" />
          {actionLabel}
        </Button>
      )}
    </div>
  )
}
