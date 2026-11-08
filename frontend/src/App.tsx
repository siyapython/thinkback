import { Layout, Menu, Typography } from 'antd'
import { BarChartOutlined, BookOutlined, EditOutlined } from '@ant-design/icons'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import LlmModeBanner from './components/LlmModeBanner'
import LibraryPage from './pages/LibraryPage'
import DocumentPage from './pages/DocumentPage'
import PracticePage from './pages/PracticePage'
import DashboardPage from './pages/DashboardPage'

const { Sider, Content } = Layout

function selectedKey(pathname: string): string {
  if (pathname.startsWith('/practice')) return 'practice'
  if (pathname.startsWith('/dashboard')) return 'dashboard'
  return 'library'
}

export default function App() {
  const { pathname } = useLocation()
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider breakpoint="lg" collapsedWidth={0} theme="light" width={220}>
        <Typography.Title level={4} style={{ margin: 16 }}>
          Thinkback
        </Typography.Title>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey(pathname)]}
          items={[
            { key: 'library', icon: <BookOutlined />, label: <Link to="/">Library</Link> },
            { key: 'practice', icon: <EditOutlined />, label: <Link to="/practice">Practice</Link> },
            { key: 'dashboard', icon: <BarChartOutlined />, label: <Link to="/dashboard">Dashboard</Link> },
          ]}
        />
      </Sider>
      <Layout>
        <LlmModeBanner />
        <Content style={{ padding: 24, maxWidth: 1100, width: '100%' }}>
          <Routes>
            <Route path="/" element={<LibraryPage />} />
            <Route path="/documents/:id" element={<DocumentPage />} />
            <Route path="/practice" element={<PracticePage />} />
            <Route path="/practice/:conceptId" element={<PracticePage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  )
}
