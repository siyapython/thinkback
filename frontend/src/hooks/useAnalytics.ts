import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/endpoints'

export function useAnalyticsUsers() {
  return useQuery({ queryKey: ['analytics', 'users'], queryFn: api.getAnalyticsUsers })
}

export function useAnalyticsOverview(userId: number | undefined) {
  return useQuery({
    queryKey: ['analytics', 'overview', userId],
    queryFn: () => api.getAnalyticsOverview(userId as number),
    enabled: userId !== undefined,
  })
}

/** POST /analytics/refresh, then refetch everything under the ['analytics'] key. */
export function useRefreshAnalytics() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.refreshAnalytics,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['analytics'] }),
  })
}
