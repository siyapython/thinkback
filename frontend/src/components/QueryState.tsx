import { Alert, Spin } from 'antd'
import type { ReactNode } from 'react'
import { errorMessage } from '../api/client'

interface Props {
  isLoading: boolean
  error: unknown
  children: ReactNode
}

/** Shows a spinner while loading and an error alert on failure; otherwise the children. */
export default function QueryState({ isLoading, error, children }: Props) {
  if (isLoading) return <Spin style={{ display: 'block', margin: '32px auto' }} />
  if (error) return <Alert type="error" showIcon message={errorMessage(error)} />
  return <>{children}</>
}
