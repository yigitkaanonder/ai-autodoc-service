import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import Button from '../components/ui/Button.jsx'
import EmptyState from '../components/ui/EmptyState.jsx'
import './DocsPage.css'

function DocsPage() {
  const { owner, name } = useParams()
  const navigate = useNavigate()

  const [docs, setDocs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [selectedFn, setSelectedFn] = useState(null)
  const [history, setHistory] = useState([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [selectedVersionId, setSelectedVersionId] = useState(null)

  // ---- load current documentation (latest state per function) ----
  useEffect(() => {
    fetch(`/api/repos/${owner}/${name}/docs`)
      .then((res) => {
        if (!res.ok) throw new Error('Failed to fetch docs')
        return res.json()
      })
      .then((data) => { setDocs(data.docs || []); setError(null) })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [owner, name])

  // group functions by file for the sidebar
  const byFile = useMemo(() => {
    const map = {}
    for (const d of docs) {
      (map[d.file_path] = map[d.file_path] || []).push(d)
    }
    return map
  }, [docs])

  // ---- load a function's full version history ----
  const selectFunction = (fn) => {
    setSelectedFn(fn)
    setHistory([])
    setSelectedVersionId(null)
    setHistoryLoading(true)
    fetch(`/api/repos/${owner}/${name}/docs/${fn}/history`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        const h = (data && data.history) || []
        setHistory(h)
        // default to the latest live (non-deleted) version
        const latestLive = h.find((v) => !v.is_deleted)
        setSelectedVersionId(latestLive ? latestLive.id : (h[0] ? h[0].id : null))
      })
      .catch(() => setHistory([]))
      .finally(() => setHistoryLoading(false))
  }

  const selectedVersion = history.find((v) => v.id === selectedVersionId) || null

  if (loading) return <div className="docs-page"><div className="dp-state">Loading…</div></div>
  if (error) return <div className="docs-page"><div className="dp-state">Error: {error}</div></div>

  return (
    <div className="docs-page">
      <div className="dp-header">
        <Button variant="ghost" size="sm" onClick={() => navigate(`/repos/${owner}/${name}`)}>← Graph</Button>
        <h1 className="dp-title">{owner}/{name} · Documentation</h1>
      </div>

      <div className="dp-body">
        <aside className="dp-sidebar">
          {docs.length === 0 && <div className="dp-state">No documentation yet.</div>}
          {Object.keys(byFile).sort().map((file) => (
            <div key={file} className="dp-file-group">
              <div className="dp-file-name">{file}</div>
              {byFile[file].map((d) => (
                <div
                  key={d.id}
                  className={`dp-fn ${selectedFn === d.function_name ? 'active' : ''}`}
                  onClick={() => selectFunction(d.function_name)}
                >
                  {d.function_name}
                </div>
              ))}
            </div>
          ))}
        </aside>

        <main className="dp-main">
          {!selectedFn && (
            <EmptyState
              title="No function selected"
              message="Choose a function from the sidebar to read its generated documentation."
            />
          )}
          {selectedFn && (
            <>
              <div className="dp-content">
                <div className="dp-content-title">{selectedFn}</div>
                {historyLoading && <div className="dp-state">Loading…</div>}
                {!historyLoading && selectedVersion && (
                  selectedVersion.is_deleted
                    ? <div className="dp-deleted-note">This version marks the function as deleted at this commit.</div>
                    : <div className="dp-markdown"><ReactMarkdown>{selectedVersion.content || ''}</ReactMarkdown></div>
                )}
                {!historyLoading && !selectedVersion && <div className="dp-state">No versions found.</div>}
              </div>

              <aside className="dp-history">
                <div className="dp-history-title">Version history</div>
                {history.map((v) => (
                  <div
                    key={v.id}
                    className={`dp-version ${v.id === selectedVersionId ? 'active' : ''} ${v.is_deleted ? 'deleted' : ''}`}
                    onClick={() => setSelectedVersionId(v.id)}
                  >
                    <div className="dp-version-top">
                      <span className="dp-version-sha">{v.commit_sha ? v.commit_sha.slice(0, 7) : '—'}</span>
                      {v.is_deleted
                        ? <span className="dp-version-badge deleted">deleted</span>
                        : <span className="dp-version-badge">score {v.score}</span>}
                    </div>
                    <div className="dp-version-date">{(v.created_at || '').slice(0, 10)}</div>
                  </div>
                ))}
              </aside>
            </>
          )}
        </main>
      </div>
    </div>
  )
}

export default DocsPage
