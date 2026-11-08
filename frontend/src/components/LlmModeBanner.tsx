import { Alert } from 'antd'
import { useHealth } from '../hooks/useHealth'

export default function LlmModeBanner() {
  const { data } = useHealth()
  if (data?.llm_mode !== 'fake') return null
  return (
    <Alert
      banner
      type="warning"
      showIcon
      message="Demo mode: AI responses are placeholders. Set LLM_MODE=real in .env to use Claude."
    />
  )
}
