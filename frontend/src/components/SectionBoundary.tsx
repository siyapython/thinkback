import { Alert, Button } from 'antd'
import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

interface Props {
  /** Human name of the section, shown in the error message. */
  name: string
  children: ReactNode
}

interface State {
  error: Error | null
}

/**
 * Error boundary for one dashboard section. If anything inside throws while rendering,
 * only this section shows a friendly error with a retry button; the rest of the page keeps working.
 */
export default class SectionBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`Dashboard section "${this.props.name}" crashed:`, error, info.componentStack)
  }

  retry = () => this.setState({ error: null })

  render() {
    if (!this.state.error) return this.props.children
    return (
      <Alert
        type="error"
        showIcon
        message={`The ${this.props.name} section could not be displayed.`}
        description="Something went wrong while drawing this part of the page. The rest of the dashboard still works."
        action={
          <Button size="small" onClick={this.retry}>
            Try again
          </Button>
        }
      />
    )
  }
}
