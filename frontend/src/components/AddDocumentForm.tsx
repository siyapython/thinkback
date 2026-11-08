import { InboxOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Form, Input, Tabs, Upload, message } from 'antd'
import type { UploadFile } from 'antd'
import { useState } from 'react'
import { errorMessage } from '../api/client'
import { useAddText, useUploadPdf } from '../hooks/useDocuments'

const CONFLICT = 'You already added this document.'

function TextForm() {
  const add = useAddText()
  const [form] = Form.useForm<{ title: string; text: string }>()
  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={(v) =>
        add.mutate(v, {
          onSuccess: () => {
            form.resetFields()
            message.success('Document added.')
          },
        })
      }
    >
      <Form.Item name="title" label="Title" rules={[{ required: true, whitespace: true, message: 'Give it a title.' }]}>
        <Input maxLength={200} />
      </Form.Item>
      <Form.Item name="text" label="Text" rules={[{ required: true, whitespace: true, message: 'Paste some text.' }]}>
        <Input.TextArea rows={6} />
      </Form.Item>
      {add.error && <Alert type="error" showIcon message={errorMessage(add.error, { conflict: CONFLICT })} style={{ marginBottom: 12 }} />}
      <Button type="primary" htmlType="submit" loading={add.isPending}>
        Add text
      </Button>
    </Form>
  )
}

function PdfForm() {
  const upload = useUploadPdf()
  const [files, setFiles] = useState<UploadFile[]>([])
  const [title, setTitle] = useState('')
  const file = files[0]?.originFileObj

  return (
    <div>
      <Form layout="vertical">
        <Form.Item label="Title (optional)">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} />
        </Form.Item>
        <Form.Item label="PDF file">
          <Upload.Dragger
            accept=".pdf,application/pdf"
            maxCount={1}
            fileList={files}
            beforeUpload={() => false} // keep the file in the browser until the user clicks Upload
            onChange={(info) => setFiles(info.fileList.slice(-1))}
          >
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">Click or drag a PDF here</p>
          </Upload.Dragger>
        </Form.Item>
      </Form>
      {upload.error && <Alert type="error" showIcon message={errorMessage(upload.error, { conflict: CONFLICT })} style={{ marginBottom: 12 }} />}
      <Button
        type="primary"
        disabled={!file}
        loading={upload.isPending}
        onClick={() =>
          file &&
          upload.mutate(
            { file, title: title.trim() || undefined },
            {
              onSuccess: () => {
                setFiles([])
                setTitle('')
                message.success('PDF uploaded.')
              },
            },
          )
        }
      >
        Upload PDF
      </Button>
    </div>
  )
}

export default function AddDocumentForm() {
  return (
    <Card title="Add a document">
      <Tabs
        items={[
          { key: 'text', label: 'Paste text', children: <TextForm /> },
          { key: 'pdf', label: 'Upload PDF', children: <PdfForm /> },
        ]}
      />
    </Card>
  )
}
