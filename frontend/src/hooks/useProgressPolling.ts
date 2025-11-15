import { useState, useEffect, useCallback, useRef } from 'react'
import { useGeneration, type GenerationProgress } from './useGeneration'

interface UseProgressPollingOptions {
  projectId: string
  enabled?: boolean
  interval?: number
  onComplete?: () => void
  onError?: (error: string) => void
}

export const useProgressPolling = ({
  projectId,
  enabled = true,
  interval = 2000,
  onComplete,
  onError,
}: UseProgressPollingOptions) => {
  const { getProgress } = useGeneration()
  const [progress, setProgress] = useState<GenerationProgress | null>(null)
  const [loading, setLoading] = useState(false)
  const [isPolling, setIsPolling] = useState(false)
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const poll = useCallback(async () => {
    if (!enabled) return

    try {
      setLoading(true)
      const data = await getProgress(projectId)
      setProgress(data)

      // Check if generation is complete
      if (
        data.status === 'COMPLETED' ||
        data.status === 'completed'
      ) {
        setIsPolling(false)
        onComplete?.()
      }

      // Check for errors
      if (data.status === 'FAILED' || data.status === 'failed') {
        setIsPolling(false)
        onError?.(data.error || 'Generation failed')
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch progress'
      onError?.(message)
      // Continue polling even if we get an error, in case it's temporary
    } finally {
      setLoading(false)
    }
  }, [projectId, enabled, getProgress, onComplete, onError])

  // Start polling on mount or when projectId changes
  useEffect(() => {
    if (!enabled || !projectId) {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
      return
    }

    setIsPolling(true)

    // Poll immediately
    poll()

    // Then set up interval
    const intervalId = setInterval(poll, interval)
    pollIntervalRef.current = intervalId

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [projectId, enabled, interval, poll])

  // Manual stop polling
  const stopPolling = useCallback(() => {
    setIsPolling(false)
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
    }
  }, [])

  // Manual start polling
  const startPolling = useCallback(() => {
    setIsPolling(true)
    poll()
    pollIntervalRef.current = setInterval(poll, interval)
  }, [poll, interval])

  // Manual refresh
  const refresh = useCallback(async () => {
    await poll()
  }, [poll])

  return {
    progress,
    loading,
    isPolling,
    stopPolling,
    startPolling,
    refresh,
  }
}

