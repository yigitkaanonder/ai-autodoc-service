import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'

function RepoDetailPage() {
  const { owner, name } = useParams()
  const navigate = useNavigate()
  const [docs, setDocs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedFunc, setSelectedFunc] = useState(null)
  const [history, setHistory] = useState([])

  useEffect(() => {
    fetch(`/api/repos/${owner}/${name}/docs`)
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch docs')
        return res.json()
      })
      .then(data => {
        setDocs(data.docs)
        setLoading(false)
      })
      .catch(err => {
        setError(err.message)
        setLoading(false)
      })
  }, [owner, name])

  function handleViewHistory(functionName) {
    if (selectedFunc === functionName) {
      setSelectedFunc(null)
      setHistory([])
      return
    }
    setSelectedFunc(functionName)
    fetch(`/api/repos/${owner}/${name}/docs/${functionName}/history`)
      .then(res => res.json())
      .then(data => setHistory(data.history))
      .catch(err => alert(err.message))
  }

  if (loading) return <p>Loading documentation...</p>
  if (error) return <p>Error: {error}</p>

  return (
    <div style={{ maxWidth: '800px', margin: '40px auto', padding: '0 20px' }}>
      <button onClick={() => navigate('/repos')} style={{ marginBottom: '20px', cursor: 'pointer' }}>
        ← Back to Repos
      </button>
      <h1>{owner}/{name}</h1>
      <p>{docs.length} documented function{docs.length !== 1 ? 's' : ''}</p>

      {docs.length === 0 && (
        <p style={{ color: '#888' }}>No documentation yet. Push some code to generate docs.</p>
      )}

      {docs.map(doc => (
        <div key={doc.id} style={{
          border: '1px solid #ddd',
          borderRadius: '8px',
          padding: '16px',
          marginBottom: '16px'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0 }}>{doc.function_name}</h3>
            <span style={{ color: '#888', fontSize: '14px' }}>
              Score: {doc.score}/10 · {doc.file_path}
            </span>
          </div>
          <div style={{
            background: '#f5f5f5',
            padding: '12px',
            borderRadius: '4px',
            marginTop: '12px'
          }}>
            <ReactMarkdown>{doc.content}</ReactMarkdown>
          </div>
          <button
            onClick={() => handleViewHistory(doc.function_name)}
            style={{ marginTop: '8px', cursor: 'pointer' }}
          >
            {selectedFunc === doc.function_name ? 'Hide History' : 'View History'}
          </button>

          {selectedFunc === doc.function_name && (
            <div style={{ marginTop: '12px', paddingLeft: '16px', borderLeft: '3px solid #ddd' }}>
              <h4>Version History ({history.length})</h4>
              {history.map(h => (
                <div key={h.id} style={{ marginBottom: '12px', padding: '8px', background: '#fafafa', borderRadius: '4px' }}>
                  <div style={{ fontSize: '13px', color: '#666' }}>
                    Commit: {h.commit_sha?.slice(0, 7) || 'N/A'} · Score: {h.score}/10 · {h.created_at?.slice(0, 10)}
                    {h.is_deleted && <span style={{ color: 'red', marginLeft: '8px' }}>DELETED</span>}
                  </div>
                  <div style={{ marginTop: '4px' }}>
                    <ReactMarkdown>{h.content}</ReactMarkdown>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

export default RepoDetailPage