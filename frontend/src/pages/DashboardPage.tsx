import { Alert, Card, Col, Row, Select, Space, Statistic, Typography } from 'antd'
import { useQueries } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/endpoints'
import AnalyticsSection from '../components/AnalyticsSection'
import Chart from '../components/Chart'
import QueryState from '../components/QueryState'
import { useDocuments } from '../hooks/useDocuments'
import { useIndependence, useMastery } from '../hooks/useMastery'
import { pct } from '../lib/weakSpots'

const SERIES_BLUE = '#2a78d6'

export default function DashboardPage() {
  const docs = useDocuments()
  const independence = useIndependence()
  const [selected, setSelected] = useState<number>()

  const docList = docs.data ?? []
  const conceptQueries = useQueries({
    queries: docList.map((d) => ({ queryKey: ['concepts', d.id], queryFn: () => api.listConcepts(d.id) })),
  })
  const conceptsLoading = conceptQueries.some((q) => q.isLoading)
  const conceptTotal = conceptQueries.reduce((n, q) => n + (q.data?.filter((c) => c.is_active).length ?? 0), 0)

  const docId = selected ?? docList[0]?.id
  const mastery = useMastery(docId)
  const rate = independence.data?.independence_rate

  const option = {
    grid: { left: 48, right: 16, top: 16, bottom: 72 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v: unknown) => `${v}%` },
    xAxis: {
      type: 'category',
      data: (mastery.data ?? []).map((m) => m.name),
      axisLabel: { interval: 0, rotate: 30, width: 110, overflow: 'truncate' },
    },
    yAxis: { type: 'value', min: 0, max: 100, axisLabel: { formatter: '{value}%' }, splitLine: { lineStyle: { opacity: 0.4 } } },
    series: [
      {
        type: 'bar',
        name: 'Mastery',
        barMaxWidth: 28,
        data: (mastery.data ?? []).map((m) => pct(m.mastery)),
        itemStyle: { color: SERIES_BLUE, borderRadius: [4, 4, 0, 0] },
      },
    ],
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Typography.Title level={2} style={{ margin: 0 }}>
        Dashboard
      </Typography.Title>
      <Row gutter={[16, 16]}>
        <Col xs={12} md={6}>
          <Card loading={docs.isLoading}>
            <Statistic title="Documents" value={docList.length} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card loading={docs.isLoading || conceptsLoading}>
            <Statistic title="Concepts" value={conceptTotal} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card loading={independence.isLoading}>
            <Statistic title="Completed attempts" value={independence.data?.completed_attempts ?? 0} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card loading={independence.isLoading}>
            <Statistic title="Independence score" value={rate == null ? '—' : pct(rate)} suffix={rate == null ? undefined : '%'} />
          </Card>
        </Col>
      </Row>
      {(docs.error || independence.error) && (
        <Alert type="error" showIcon message="Some numbers could not be loaded. Is the backend running?" />
      )}
      <Card
        title="Mastery by concept"
        extra={
          <Select
            style={{ minWidth: 220 }}
            placeholder="Select a document"
            value={docId}
            onChange={setSelected}
            options={docList.map((d) => ({ value: d.id, label: d.title }))}
          />
        }
      >
        <QueryState isLoading={docs.isLoading || mastery.isLoading} error={mastery.error}>
          {mastery.data?.length ? (
            <Chart option={option} />
          ) : (
            <Typography.Text type="secondary">No concepts to chart yet. Extract concepts from a document first.</Typography.Text>
          )}
        </QueryState>
      </Card>
      <AnalyticsSection />
    </Space>
  )
}
