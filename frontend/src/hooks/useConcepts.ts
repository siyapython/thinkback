import { useQuery } from '@tanstack/react-query'
import { api } from '../api/endpoints'

export function useConcepts(documentId: number) {
  return useQuery({
    queryKey: ['concepts', documentId],
    queryFn: () => api.listConcepts(documentId),
    enabled: Number.isFinite(documentId),
  })
}
