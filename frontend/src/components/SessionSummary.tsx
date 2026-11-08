import { Button, Card, Descriptions, Progress, Space, Spin, Typography } from 'antd'
import type { AttemptOut } from '../api/types'
import { pct } from '../lib/weakSpots'

interface Props {
  attempt: AttemptOut
  bestScore: number // best rubric score among graded answers (0 if none)
  mastery?: number // updated mastery for the concept; undefined while loading
  explanation?: string | null
  onNext: () => void
  onBack?: () => void
}

export default function SessionSummary({ attempt, bestScore, mastery, explanation, onNext, onBack }: Props) {
  return (
    <Card title="Attempt complete">
      <Space orientation="vertical" style={{ width: '100%' }} size="middle">
        {explanation && <Typography.Paragraph style={{ whiteSpace: 'pre-line' }}>{explanation}</Typography.Paragraph>}
        <Descriptions column={1} bordered size="small">
          <Descriptions.Item label="Score">{pct(bestScore)}%</Descriptions.Item>
          <Descriptions.Item label="Effective score">
            {attempt.effective_score == null ? '—' : `${pct(attempt.effective_score)}%`}
          </Descriptions.Item>
          <Descriptions.Item label="Hints used">{attempt.max_hint_level}</Descriptions.Item>
          <Descriptions.Item label="Updated mastery">
            {mastery === undefined ? <Spin size="small" /> : <Progress percent={pct(mastery)} size="small" />}
          </Descriptions.Item>
        </Descriptions>
        <Space>
          <Button type="primary" onClick={onNext}>
            Next question
          </Button>
          {onBack && <Button onClick={onBack}>Back to document</Button>}
        </Space>
      </Space>
    </Card>
  )
}
