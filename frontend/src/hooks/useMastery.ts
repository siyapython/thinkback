import { useQuery } from '@tanstack/react-query'
import { api } from '../api/endpoints'

export function useMastery(documentId: number | undefined) {
  return useQuery({
    queryKey: ['mastery', documentId],
    queryFn: () => api.getMastery(documentId as number),
    enabled: documentId !== undefined && Number.isFinite(documentId),
  })
}

export function useIndependence() {
  return useQuery({ queryKey: ['independence'], queryFn: api.getIndependence })
}
