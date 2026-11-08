import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/endpoints'

/** Mutations for one practice session. Each one refreshes mastery/metrics when it can change them. */
export function usePractice() {
  const qc = useQueryClient()
  const refreshProgress = () => {
    qc.invalidateQueries({ queryKey: ['mastery'] })
    qc.invalidateQueries({ queryKey: ['independence'] })
  }

  // Create the question, then open an attempt on it (the UI treats this as one step).
  const start = useMutation({
    mutationFn: async (conceptId: number) => {
      const question = await api.createQuestion(conceptId)
      const attempt = await api.startAttempt(question.id)
      return { question, attempt }
    },
  })
  const submit = useMutation({
    mutationFn: ({ attemptId, text }: { attemptId: number; text: string }) =>
      api.submitAnswer(attemptId, text),
    onSuccess: (res) => {
      if (res.attempt.status === 'completed') refreshProgress()
    },
  })
  const hint = useMutation({ mutationFn: (attemptId: number) => api.requestHint(attemptId) })
  const reveal = useMutation({ mutationFn: (attemptId: number) => api.reveal(attemptId), onSuccess: refreshProgress })
  const complete = useMutation({ mutationFn: (attemptId: number) => api.complete(attemptId), onSuccess: refreshProgress })

  return { start, submit, hint, reveal, complete }
}
