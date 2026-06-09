import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'

function ReposPage() {
  const navigate = useNavigate()
  const [repos, setRepos] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const username = localStorage.getItem('username')

  useEffect(() => {
    if (!username) {
      navigate('/')
      return
    }
    fetchRepos()
  }, [username, navigate])

  function fetchRepos() {
    fetch(`/api/repos?username=${username}`)
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch repos')
        return res.json()
      })
      .then(data => {
        setRepos(data.repos)
        setLoading(false)
      })
      .catch(err => {
        setError(err.message)
        setLoading(false)
      })
  }

  function handleActivate(repoFullName) {
    fetch(`/api/repos/activate?username=${username}&repo_full_name=${repoFullName}`, {
      method: 'POST'
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'activated') {
          fetchRepos()
        } else {
          alert(`Error: ${data.error}`)
        }
      })
      .catch(err => alert(err.message))
  }

  function handleDeactivate(repoFullName) {
    if (!confirm(`Deactivate ${repoFullName}? This will remove the webhook. Documentation data will remain.`)) return

    fetch(`/api/repos/deactivate?username=${username}&repo_full_name=${repoFullName}`, {
      method: 'POST'
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'deactivated') {
          fetchRepos()
        } else {
          alert(`Error: ${data.error}`)
        }
      })
      .catch(err => alert(err.message))
  }

  function handleDeleteData(repoFullName) {
    if (!confirm(`Delete all documentation data for ${repoFullName}?`)) return

    fetch(`/api/repos/delete-data?username=${username}&repo_full_name=${repoFullName}`, {
      method: 'POST'
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'deleted') {
          alert(`Deleted ${data.deleted_docs} docs and ${data.deleted_registry} registry entries.`)
        } else {
          alert(`Error: ${data.error}`)
        }
      })
      .catch(err => alert(err.message))
  }

  if (loading) return <p>Loading repos...</p>
  if (error) return <p>Error: {error}</p>

  return (
    <div style={{ maxWidth: '700px', margin: '40px auto', padding: '0 20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>{username}'s Repositories</h1>
        <button onClick={() => { localStorage.removeItem('username'); navigate('/') }}
          style={{ padding: '8px 16px', cursor: 'pointer' }}>
          Logout
        </button>
      </div>
      <ul style={{ listStyle: 'none', padding: 0 }}>
        {repos.map(repo => (
          <li key={repo.full_name} style={{
            border: '1px solid #ddd',
            borderRadius: '8px',
            padding: '16px',
            marginBottom: '12px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Link to={`/repos/${repo.full_name}`} style={{ fontWeight: 'bold', textDecoration: 'none', color: '#0969da' }}>
                {repo.name}
                {repo.private && <span style={{ marginLeft: '8px', color: '#888' }}>🔒</span>}
              </Link>
              <div style={{ display: 'flex', gap: '8px' }}>
                {repo.is_active ? (
                  <button
                    onClick={() => handleDeactivate(repo.full_name)}
                    style={{ padding: '8px 16px', cursor: 'pointer', background: '#dc3545', color: 'white', border: 'none', borderRadius: '4px' }}
                  >
                    Deactivate
                  </button>
                ) : (
                  <button
                    onClick={() => handleActivate(repo.full_name)}
                    style={{ padding: '8px 16px', cursor: 'pointer', background: '#28a745', color: 'white', border: 'none', borderRadius: '4px' }}
                  >
                    Activate
                  </button>
                )}
                <button
                  onClick={() => handleDeleteData(repo.full_name)}
                  style={{ padding: '8px 16px', cursor: 'pointer', color: 'red', borderColor: 'red' }}
                >
                  Delete Data
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default ReposPage