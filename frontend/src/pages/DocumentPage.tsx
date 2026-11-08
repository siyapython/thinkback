import { Alert, Button, List, Space, Typography } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { Link, useNavigate, useParams } from 'react-router-dom'
import ConceptRow from '../components/ConceptRow'
import QueryState from '../components/QueryState'
import { useConcepts } from '../hooks/useConcepts'
import { useDocument } from '../hooks/useDocuments'
import { useMastery } from '../hooks/useMastery'
import { pickWeakSpots, practiceUrl } from '../lib/weakSpots'

export default function DocumentPage() {
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const doc = useDocument(id)
  const concepts = useConcepts(id)
  const mastery = useMastery(id)

  const active = (concepts.data ?? []).filter((c) => c.is_active)
  const byId = new Map((mastery.data ?? []).map((m) => [m.concept_id, m]))

  const weakSpots = () => {
    const ids = pickWeakSpots(mastery.data ?? [])
    if (ids.length) navigate(practiceUrl(ids, id))
  }

  return (
    <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
      <Link to="/">
        <ArrowLeftOutlined /> Library
      </Link>
      <QueryState isLoading={doc.isLoading} error={doc.error}>
        <Typography.Title level={2} style={{ margin: 0 }}>
          {doc.data?.title}
        </Typography.Title>
      </QueryState>
      <Button type="primary" disabled={!mastery.data?.length} loading={mastery.isLoading} onClick={weakSpots}>
        Work on weak spots
      </Button>
      {mastery.error && <Alert type="warning" showIcon message="Mastery could not be loaded; showing concepts only." />}
      <QueryState isLoading={concepts.isLoading} error={concepts.error}>
        <List
          bordered
          locale={{ emptyText: 'No concepts yet. Go to the Library and click "Extract concepts".' }}
          dataSource={active}
          renderItem={(c) => (
            <ConceptRow
              key={c.id}
              concept={c}
              mastery={byId.get(c.id)}
              onPractice={(cid) => navigate(practiceUrl([cid], id))}
            />
          )}
        />
      </QueryState>
    </Space>
  )
}
