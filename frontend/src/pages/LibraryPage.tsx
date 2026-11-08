import { Space, Typography } from 'antd'
import AddDocumentForm from '../components/AddDocumentForm'
import DocumentList from '../components/DocumentList'

export default function LibraryPage() {
  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Typography.Title level={2} style={{ margin: 0 }}>
        Library
      </Typography.Title>
      <AddDocumentForm />
      <DocumentList />
    </Space>
  )
}
