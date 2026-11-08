import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/endpoints'
import type { TextDocumentIn } from '../api/types'

export const docKeys = {
  all: ['documents'] as const,
  one: (id: number) => ['documents', id] as const,
}

export function useDocuments() {
  return useQuery({ queryKey: docKeys.all, queryFn: api.listDocuments })
}

export function useDocument(id: number) {
  return useQuery({ queryKey: docKeys.one(id), queryFn: () => api.getDocument(id), enabled: Number.isFinite(id) })
}

export function useAddText() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: TextDocumentIn) => api.createTextDocument(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: docKeys.all }),
  })
}

export function useUploadPdf() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ file, title }: { file: File; title?: string }) => api.uploadPdf(file, title),
    onSuccess: () => qc.invalidateQueries({ queryKey: docKeys.all }),
  })
}

export function useExtractConcepts() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.extractConcepts(id),
    // Success or failure, the document row changes (status / error_message), and so may concepts.
    onSettled: (_data, _err, id) => {
      qc.invalidateQueries({ queryKey: docKeys.all })
      qc.invalidateQueries({ queryKey: ['concepts', id] })
      qc.invalidateQueries({ queryKey: ['mastery', id] })
    },
  })
}
