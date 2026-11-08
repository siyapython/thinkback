import { BulbOutlined } from '@ant-design/icons'
import { Alert, Button, Space, Typography } from 'antd'
import { MAX_HINT_LEVEL, type HintOut } from '../api/types'

interface Props {
  hints: HintOut[]
  level: number // attempt.max_hint_level, as reported by the server
  loading?: boolean
  disabled?: boolean // e.g. the attempt is already completed
  error?: string
  onRequest: () => void
}

export default function HintPanel({ hints, level, loading, disabled, error, onRequest }: Props) {
  const exhausted = level >= MAX_HINT_LEVEL
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Space>
        <Button icon={<BulbOutlined />} onClick={onRequest} loading={loading} disabled={disabled || exhausted}>
          I&apos;m stuck
        </Button>
        <Typography.Text type="secondary">
          Hint {level} of {MAX_HINT_LEVEL}
        </Typography.Text>
      </Space>
      {error && <Alert type="error" showIcon message={error} />}
      {hints.map((h) => (
        <Alert key={h.level} type="info" message={`Hint ${h.level}`} description={h.hint_text} />
      ))}
    </Space>
  )
}
