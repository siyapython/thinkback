import { Alert, Button, Card, Empty, Input, Progress, Space, Spin, Tag, Typography } from 'antd'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { errorMessage } from '../api/client'
import type { AnswerOut, AttemptOut, HintOut, QuestionOut } from '../api/types'
import HintPanel from '../components/HintPanel'
import RevealButton from '../components/RevealButton'
import SessionSummary from '../components/SessionSummary'
import { useMastery } from '../hooks/useMastery'
import { usePractice } from '../hooks/usePractice'
import { pct, practiceUrl } from '../lib/weakSpots'

interface SessionProps {
  conceptId: number
  documentId?: number
  queue: number[]
  onNext: () => void
}

function PracticeSession({ conceptId, documentId, queue, onNext }: SessionProps) {
  const navigate = useNavigate()
  const { start, submit, hint, reveal, complete } = usePractice()
  const [question, setQuestion] = useState<QuestionOut>()
  const [attempt, setAttempt] = useState<AttemptOut>()
  const [hints, setHints] = useState<HintOut[]>([])
  const [answerText, setAnswerText] = useState('')
  const [lastAnswer, setLastAnswer] = useState<AnswerOut>()
  const [bestScore, setBestScore] = useState(0)
  const [explanation, setExplanation] = useState<string | null>(null)
  const started = useRef(false)

  // Create the question and open the attempt once per mounted session (the ref guards StrictMode's double effect).
  useEffect(() => {
    if (started.current) return
    started.current = true
    start.mutate(conceptId, {
      onSuccess: (r) => {
        setQuestion(r.question)
        setAttempt(r.attempt)
      },
    })
  }, [conceptId, start])

  const done = attempt?.status === 'completed'
  const mastery = useMastery(done ? documentId : undefined)
  const updatedMastery = mastery.data?.find((m) => m.concept_id === conceptId)?.mastery

  if (start.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message={errorMessage(start.error)}
        action={<Link to={documentId ? `/documents/${documentId}` : '/'}>Go back</Link>}
      />
    )
  }
  if (!question || !attempt) {
    return <Spin tip="Writing a question..." style={{ display: 'block', margin: '48px auto' }} />
  }

  const backToDoc = documentId ? () => navigate(`/documents/${documentId}`) : undefined

  if (done) {
    return (
      <SessionSummary
        attempt={attempt}
        bestScore={bestScore}
        mastery={documentId ? updatedMastery : undefined}
        explanation={explanation}
        onNext={onNext}
        onBack={backToDoc}
      />
    )
  }

  const busy = submit.isPending || reveal.isPending || complete.isPending
  const inlineError = [submit, hint, reveal, complete].find((m) => m.isError)

  return (
    <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
      <Card>
        <Tag>{question.question_type}</Tag>
        {queue.length > 0 && <Tag color="blue">{queue.length} more queued</Tag>}
        <Typography.Paragraph style={{ fontSize: 16, marginTop: 8, marginBottom: 0, whiteSpace: 'pre-line' }}>
          {question.prompt}
        </Typography.Paragraph>
      </Card>

      <Input.TextArea
        rows={6}
        placeholder="Write your answer here"
        value={answerText}
        maxLength={5000}
        onChange={(e) => setAnswerText(e.target.value)}
        disabled={busy}
      />
      <Space wrap>
        <Button
          type="primary"
          loading={submit.isPending}
          disabled={!answerText.trim() || busy}
          onClick={() =>
            submit.mutate(
              { attemptId: attempt.id, text: answerText },
              {
                onSuccess: (res) => {
                  setLastAnswer(res)
                  setAttempt(res.attempt)
                  setBestScore((b) => Math.max(b, res.rubric_score))
                },
              },
            )
          }
        >
          Submit
        </Button>
        <RevealButton
          loading={reveal.isPending}
          disabled={busy}
          onConfirm={() =>
            reveal.mutate(attempt.id, {
              onSuccess: (res) => {
                setExplanation(res.explanation)
                setAttempt(res.attempt)
              },
            })
          }
        />
        {lastAnswer && (
          <Button
            loading={complete.isPending}
            disabled={busy}
            onClick={() => complete.mutate(attempt.id, { onSuccess: setAttempt })}
          >
            End attempt
          </Button>
        )}
      </Space>

      {inlineError && <Alert type="error" showIcon message={errorMessage(inlineError.error)} />}

      {lastAnswer && (
        <Card title="Feedback" size="small">
          <Progress percent={pct(lastAnswer.rubric_score)} aria-label="Score" />
          <Typography.Paragraph style={{ marginBottom: 0 }}>{lastAnswer.feedback}</Typography.Paragraph>
        </Card>
      )}

      <HintPanel
        hints={hints}
        level={attempt.max_hint_level}
        loading={hint.isPending}
        disabled={busy}
        onRequest={() =>
          hint.mutate(attempt.id, {
            onSuccess: (res) => {
              setHints((h) => [...h, res])
              setAttempt(res.attempt)
            },
          })
        }
      />
    </Space>
  )
}

export default function PracticePage() {
  const params = useParams()
  const [search] = useSearchParams()
  const navigate = useNavigate()
  const [round, setRound] = useState(0)

  const conceptId = Number(params.conceptId)
  const docParam = search.get('doc')
  const documentId = docParam ? Number(docParam) : undefined
  const queue = (search.get('queue') ?? '').split(',').map(Number).filter((n) => Number.isInteger(n) && n > 0)

  if (!Number.isInteger(conceptId) || conceptId <= 0) {
    return (
      <Empty description="Pick a concept to practice from a document.">
        <Link to="/">Go to Library</Link>
      </Empty>
    )
  }

  const onNext = () => {
    // Move on to the next queued concept, otherwise ask a fresh question on the same one.
    if (queue.length) navigate(practiceUrl(queue, documentId))
    else setRound((r) => r + 1)
  }

  return (
    <Space orientation="vertical" style={{ width: '100%' }}>
      <Typography.Title level={2} style={{ margin: 0 }}>
        Practice
      </Typography.Title>
      <PracticeSession
        key={`${conceptId}-${round}`}
        conceptId={conceptId}
        documentId={documentId}
        queue={queue}
        onNext={onNext}
      />
    </Space>
  )
}
