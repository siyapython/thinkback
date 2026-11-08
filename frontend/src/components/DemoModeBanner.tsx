import { Alert } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/endpoints'

/** Shown above everything while the backend runs with LLM_MODE=fake (canned AI replies). */
export default function DemoModeBanner() {
  const health = useQuery({ queryKey: ['health'], queryFn: api.getHealth, staleTime: 60_000 })
  if (health.data?.llm_mode !== 'fake') return null
  return (
    <Alert
      banner
      type="warning"
      showIcon
      message="Demo mode: AI responses are placeholders. Set LLM_MODE=real in .env to use Claude."
    />
  )
}
