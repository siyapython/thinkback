import { Button, List, Progress, Space, Tag, Typography } from 'antd'
import type { ConceptMasteryOut, ConceptOut } from '../api/types'
import { pct } from '../lib/weakSpots'

interface Props {
  concept: ConceptOut
  mastery?: ConceptMasteryOut
  onPractice: (conceptId: number) => void
}

export default function ConceptRow({ concept, mastery, onPractice }: Props) {
  const m = mastery?.mastery ?? 0
  const passages = concept.source_chunk_ids.length
  return (
    <List.Item
      actions={[
        <Button key="p" type="primary" onClick={() => onPractice(concept.id)}>
          Practice
        </Button>,
      ]}
    >
      <List.Item.Meta
        title={
          <Space>
            <span>{concept.name}</span>
            {mastery?.is_gap && <Tag color="red">Gap</Tag>}
          </Space>
        }
        description={
          <>
            <Typography.Paragraph style={{ marginBottom: 4 }}>{concept.definition}</Typography.Paragraph>
            <Typography.Text type="secondary">
              Found in {passages} {passages === 1 ? 'passage' : 'passages'} of the source
            </Typography.Text>
            <Progress
              percent={pct(m)}
              size="small"
              status={mastery?.is_gap ? 'exception' : 'normal'}
              aria-label={`Mastery of ${concept.name}`}
            />
          </>
        }
      />
    </List.Item>
  )
}
