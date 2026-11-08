import { http } from './client'
import type {
  AnswerOut,
  AttemptOut,
  ConceptMasteryOut,
  ConceptOut,
  DocumentOut,
  ExtractionOut,
  HintOut,
  IndependenceOut,
  QuestionOut,
  RevealOut,
  TextDocumentIn,
} from './types'

const data = <T>(p: Promise<{ data: T }>): Promise<T> => p.then((r) => r.data)

export const api = {
  listDocuments: () => data<DocumentOut[]>(http.get('/documents')),
  getDocument: (id: number) => data<DocumentOut>(http.get(`/documents/${id}`)),
  createTextDocument: (body: TextDocumentIn) => data<DocumentOut>(http.post('/documents', body)),
  uploadPdf: (file: File, title?: string) => {
    const form = new FormData()
    form.append('file', file)
    if (title) form.append('title', title)
    return data<DocumentOut>(http.post('/documents', form))
  },
  extractConcepts: (id: number) => data<ExtractionOut>(http.post(`/documents/${id}/extract-concepts`)),
  listConcepts: (id: number) => data<ConceptOut[]>(http.get(`/documents/${id}/concepts`)),
  getMastery: (id: number) => data<ConceptMasteryOut[]>(http.get(`/documents/${id}/mastery`)),

  createQuestion: (conceptId: number) => data<QuestionOut>(http.post(`/concepts/${conceptId}/questions`)),
  startAttempt: (questionId: number) => data<AttemptOut>(http.post(`/questions/${questionId}/attempts`)),
  getAttempt: (id: number) => data<AttemptOut>(http.get(`/attempts/${id}`)),
  submitAnswer: (attemptId: number, answer_text: string) =>
    data<AnswerOut>(http.post(`/attempts/${attemptId}/answers`, { answer_text })),
  requestHint: (attemptId: number) => data<HintOut>(http.post(`/attempts/${attemptId}/hints`)),
  reveal: (attemptId: number) => data<RevealOut>(http.post(`/attempts/${attemptId}/reveal`)),
  complete: (attemptId: number) => data<AttemptOut>(http.post(`/attempts/${attemptId}/complete`)),

  getIndependence: () => data<IndependenceOut>(http.get('/metrics/independence')),
}
