import * as React from "react"
import { cn } from "@/lib/utils"

interface CollapsibleContextValue {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const CollapsibleContext = React.createContext<CollapsibleContextValue | null>(null)

interface CollapsibleProps {
  open?: boolean
  onOpenChange?: (open: boolean) => void
  children: React.ReactNode
  className?: string
}

function Collapsible({
  open = false,
  onOpenChange,
  children,
  className,
}: CollapsibleProps) {
  return (
    <CollapsibleContext.Provider value={{ open, onOpenChange: onOpenChange || (() => {}) }}>
      <div className={cn(className)}>{children}</div>
    </CollapsibleContext.Provider>
  )
}

interface CollapsibleTriggerProps {
  children: React.ReactNode
  className?: string
  asChild?: boolean
}

function CollapsibleTrigger({ children, className }: CollapsibleTriggerProps) {
  const context = React.useContext(CollapsibleContext)
  if (!context) throw new Error("CollapsibleTrigger must be used within Collapsible")

  return (
    <button
      type="button"
      className={cn(className)}
      onClick={() => context.onOpenChange(!context.open)}
    >
      {children}
    </button>
  )
}

interface CollapsibleContentProps {
  children: React.ReactNode
  className?: string
}

function CollapsibleContent({ children, className }: CollapsibleContentProps) {
  const context = React.useContext(CollapsibleContext)
  if (!context) throw new Error("CollapsibleContent must be used within Collapsible")

  if (!context.open) return null

  return <div className={cn(className)}>{children}</div>
}

export { Collapsible, CollapsibleTrigger, CollapsibleContent }
