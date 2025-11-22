import React, { useState, useEffect } from 'react'
import type { TimelineClip as TimelineClipType } from '@/stores/editorStore'
import { useEditorStore } from '@/stores/editorStore'
import { formatDuration } from '@/utils/formatters'

interface TimelineClipProps {
  clip: TimelineClipType
  isSelected: boolean
  onSelect: () => void
  pixelsPerSecond: number
  trackType: 'video' | 'audio'
}

/**
 * TimelineClip Component
 * Displays a single clip on the timeline with trim handles
 */
export const TimelineClip: React.FC<TimelineClipProps> = ({
  clip,
  isSelected,
  onSelect,
  pixelsPerSecond,
  trackType
}) => {
  const { updateClipTrim, moveClip } = useEditorStore()
  const [isDraggingTrim, setIsDraggingTrim] = useState<'start' | 'end' | null>(null)
  const [dragStartX, setDragStartX] = useState(0)
  const [dragStartTrim, setDragStartTrim] = useState<{ start: number; end: number } | null>(null)
  const [isDraggingClip, setIsDraggingClip] = useState(false)
  const [dragStartClipX, setDragStartClipX] = useState(0)
  const [dragStartClipPosition, setDragStartClipPosition] = useState(0)

  // Calculate dimensions
  const positionPx = clip.position * pixelsPerSecond
  const widthPx = clip.effectiveDuration * pixelsPerSecond

  // Handle clip body drag (for reordering)
  const handleClipMouseDown = (e: React.MouseEvent) => {
    // Only allow drag from middle area (not from trim handles)
    const clipRect = e.currentTarget.getBoundingClientRect()
    const clickX = e.clientX - clipRect.left
    
    // Check if click is on trim handles (they are ~8px wide)
    const isTrimHandle = clickX < 8 || clickX > clipRect.width - 8
    if (isTrimHandle) return
    
    e.preventDefault()
    setIsDraggingClip(true)
    setDragStartClipX(e.clientX)
    setDragStartClipPosition(clip.position)
    onSelect()
  }

  // Handle trim start drag
  const handleTrimStartMouseDown = (e: React.MouseEvent) => {
    e.stopPropagation()
    setIsDraggingTrim('start')
    setDragStartX(e.clientX)
    setDragStartTrim({ start: clip.trimStart, end: clip.trimEnd })
  }

  // Handle trim end drag
  const handleTrimEndMouseDown = (e: React.MouseEvent) => {
    e.stopPropagation()
    setIsDraggingTrim('end')
    setDragStartX(e.clientX)
    setDragStartTrim({ start: clip.trimStart, end: clip.trimEnd })
  }

  // Handle trim dragging
  useEffect(() => {
    if (!isDraggingTrim || !dragStartTrim) return

    const handleMouseMove = (e: MouseEvent) => {
      const deltaX = e.clientX - dragStartX
      const deltaTime = deltaX / pixelsPerSecond

      if (isDraggingTrim === 'start') {
        const newTrimStart = Math.max(
          0,
          Math.min(dragStartTrim.start + deltaTime, dragStartTrim.end - 0.1)
        )
        updateClipTrim(clip.id, newTrimStart, dragStartTrim.end)
      } else {
        const newTrimEnd = Math.max(
          dragStartTrim.start + 0.1,
          Math.min(dragStartTrim.end + deltaTime, clip.duration)
        )
        updateClipTrim(clip.id, dragStartTrim.start, newTrimEnd)
      }
    }

    const handleMouseUp = () => {
      setIsDraggingTrim(null)
      setDragStartTrim(null)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDraggingTrim, dragStartTrim, dragStartX, pixelsPerSecond, clip.id, clip.duration, updateClipTrim])

  // Handle clip dragging (reordering)
  useEffect(() => {
    if (!isDraggingClip) return

    const handleMouseMove = (e: MouseEvent) => {
      const deltaX = e.clientX - dragStartClipX
      const deltaTime = deltaX / pixelsPerSecond
      const newPosition = Math.max(0, dragStartClipPosition + deltaTime)
      moveClip(trackType, clip.id, newPosition)
    }

    const handleMouseUp = () => {
      setIsDraggingClip(false)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDraggingClip, dragStartClipX, dragStartClipPosition, pixelsPerSecond, trackType, clip.id, moveClip])

  return (
    <div
      className={`absolute h-full rounded cursor-move ${
        isSelected ? 'ring-2 ring-accent-gold' : ''
      } ${trackType === 'video' ? 'bg-blue-600' : 'bg-green-600'}`}
      style={{
        left: `${positionPx}px`,
        width: `${widthPx}px`,
        backgroundColor: clip.color || (trackType === 'video' ? '#2563eb' : '#16a34a')
      }}
      onMouseDown={handleClipMouseDown}
      onClick={onSelect}
    >
      {/* Trim Start Handle */}
      <div
        className="absolute left-0 top-0 bottom-0 w-2 bg-white bg-opacity-50 cursor-ew-resize hover:bg-opacity-75"
        onMouseDown={handleTrimStartMouseDown}
      />
      
      {/* Clip Content */}
      <div className="absolute inset-0 flex items-center justify-center text-white text-xs font-medium p-1 overflow-hidden">
        <span className="truncate">{clip.name}</span>
      </div>
      
      {/* Trim End Handle */}
      <div
        className="absolute right-0 top-0 bottom-0 w-2 bg-white bg-opacity-50 cursor-ew-resize hover:bg-opacity-75"
        onMouseDown={handleTrimEndMouseDown}
      />
    </div>
  )
}

