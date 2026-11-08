import { EyeOutlined } from '@ant-design/icons'
import { Button, Modal } from 'antd'
import { useState } from 'react'

interface Props {
  onConfirm: () => void
  loading?: boolean
  disabled?: boolean
}

export default function RevealButton({ onConfirm, loading, disabled }: Props) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button icon={<EyeOutlined />} danger disabled={disabled} loading={loading} onClick={() => setOpen(true)}>
        Show answer
      </Button>
      <Modal
        open={open}
        title="Show the answer?"
        okText="Yes, show it"
        okButtonProps={{ danger: true }}
        cancelText="Keep trying"
        onCancel={() => setOpen(false)}
        onOk={() => {
          setOpen(false)
          onConfirm()
        }}
      >
        Revealing the answer ends this attempt and lowers your mastery for this concept. Try a hint first if you can.
      </Modal>
    </>
  )
}
