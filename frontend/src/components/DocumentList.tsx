import { Alert, Button, List, Space, Tag, Typography } from 'antd'
import { Link } from 'react-router-dom'
import { errorMessage } from '../api/client'
import type { DocumentStatus } from '../api/types'
import { useDocuments, useExtractConcepts } from '../hooks/useDocuments'
import QueryState from './QueryState'

const STATUS_COLOR: Record<DocumentStatus, string> = {
  uploaded: 'blue',
  processing: 'gold',
  ready: 'green',
  failed: 'red',
}

export default function DocumentList() {
  const docs = useDocuments()
  const extract = useExtractConcepts()
  const busyId = extract.isPending ? extract.variables : undefined

  return (
    <QueryState isLoading={docs.isLoading} error={docs.error}>
      <List
        locale={{ emptyText: 'No documents yet. Add one above.' }}
        dataSource={docs.data ?? []}
        renderItem={(d) => (
          <List.Item
            key={d.id}
            actions={[
              <Button key="x" loading={busyId === d.id} disabled={extract.isPending && busyId !== d.id} onClick={() => extract.mutate(d.id)}>
                Extract concepts
              </Button>,
            ]}
          >
            <List.Item.Meta
              title={
                <Space>
                  <Link to={`/documents/${d.id}`}>{d.title}</Link>
                  <Tag color={STATUS_COLOR[d.status] ?? 'default'}>{d.status}</Tag>
                </Space>
              }
              description={
                <>
                  <Typography.Text type="secondary">
                    {d.source_type === 'pdf' && d.page_count ? `${d.page_count} pages · ` : ''}
                    {d.chunk_count} passages
                  </Typography.Text>
                  {d.status === 'failed' && d.error_message && (
                    <Alert type="error" showIcon message={d.error_message} style={{ marginTop: 8 }} />
                  )}
                  {extract.isError && extract.variables === d.id && (
                    <Alert type="error" showIcon message={errorMessage(extract.error)} style={{ marginTop: 8 }} />
                  )}
                </>
              }
            />
          </List.Item>
        )}
      />
    </QueryState>
  )
}
