import { Component, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: { componentStack: string }) {
    console.error('[superDHCP] React error boundary caught:', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#0a0e17',
          color: '#e2e8f0',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        }}>
          <div style={{
            background: '#111827',
            border: '1px solid #1f2937',
            borderRadius: 12,
            padding: 48,
            maxWidth: 520,
            width: '90%',
            textAlign: 'center',
          }}>
            <h2 style={{ fontSize: 24, marginBottom: 16, color: '#ef4444' }}>
              Application Error
            </h2>
            <p style={{ color: '#94a3b8', marginBottom: 24, fontSize: 14, lineHeight: 1.6 }}>
              The application encountered an unexpected error.
              <br />
              This usually indicates a backend connection issue or deployment mismatch.
            </p>
            <div style={{
              background: '#0f172a',
              borderRadius: 8,
              padding: '12px 16px',
              marginBottom: 24,
              textAlign: 'left',
              fontSize: 12,
              color: '#64748b',
              fontFamily: 'monospace',
              wordBreak: 'break-all',
              maxHeight: 120,
              overflow: 'auto',
            }}>
              {this.state.error?.message || 'Unknown error'}
            </div>
            <div style={{
              display: 'flex',
              gap: 12,
              justifyContent: 'center',
              flexWrap: 'wrap',
            }}>
              <button
                onClick={() => window.location.reload()}
                style={{
                  padding: '10px 24px',
                  background: '#3b82f6',
                  border: 'none',
                  borderRadius: 8,
                  color: '#fff',
                  fontSize: 14,
                  cursor: 'pointer',
                  fontWeight: 500,
                }}
              >
                Reload Page
              </button>
              <button
                onClick={() => {
                  localStorage.clear();
                  window.location.href = '/api/docs';
                }}
                style={{
                  padding: '10px 24px',
                  background: 'transparent',
                  border: '1px solid #3b82f6',
                  borderRadius: 8,
                  color: '#3b82f6',
                  fontSize: 14,
                  cursor: 'pointer',
                }}
              >
                API Docs (Debug)
              </button>
              <button
                onClick={() => {
                  localStorage.clear();
                  window.location.reload();
                }}
                style={{
                  padding: '10px 24px',
                  background: 'transparent',
                  border: '1px solid #ef4444',
                  borderRadius: 8,
                  color: '#ef4444',
                  fontSize: 14,
                  cursor: 'pointer',
                }}
              >
                Clear Cache &amp; Reload
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
