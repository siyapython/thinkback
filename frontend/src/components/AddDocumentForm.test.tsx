import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/endpoints'
import { renderWithProviders } from '../test/utils'
import AddDocumentForm from './AddDocumentForm'

function httpError(status: number, detail: unknown) {
  return new AxiosError('fail', 'ERR_BAD_REQUEST', undefined, undefined, {
    status, data: { detail },
  } as AxiosResponse)
}

async function pickPdfAndUpload() {
  await userEvent.click(screen.getByRole('tab', { name: /upload pdf/i }))
  const input = document.querySelector('input[type="file"]') as HTMLInputElement
  await userEvent.upload(input, new File(['%PDF-1.4'], 'notes.pdf', { type: 'application/pdf' }))
  await userEvent.click(screen.getByRole('button', { name: /^upload pdf$/i }))
}

describe('AddDocumentForm upload errors', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('shows a friendly message on a 409 duplicate', async () => {
    vi.spyOn(api, 'uploadPdf').mockRejectedValue(httpError(409, 'You already uploaded this exact content (document id 3).'))
    renderWithProviders(<AddDocumentForm />)
    await pickPdfAndUpload()
    expect(await screen.findByText('You already added this document.')).toBeInTheDocument()
  })

  it('shows the size limit message on a 413', async () => {
    vi.spyOn(api, 'uploadPdf').mockRejectedValue(httpError(413, 'Upload is too large; the limit is 20 MB.'))
    renderWithProviders(<AddDocumentForm />)
    await pickPdfAndUpload()
    expect(await screen.findByText(/too large; the limit is 20 MB/)).toBeInTheDocument()
  })

  it('sends the chosen file to the API', async () => {
    const spy = vi.spyOn(api, 'uploadPdf').mockResolvedValue({} as never)
    renderWithProviders(<AddDocumentForm />)
    await pickPdfAndUpload()
    await waitFor(() => expect(spy).toHaveBeenCalledOnce())
    expect(spy.mock.calls[0][0].name).toBe('notes.pdf')
  })
})
