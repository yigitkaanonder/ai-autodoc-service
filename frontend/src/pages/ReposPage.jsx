import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import Button from '../components/ui/Button.jsx'
import ConfirmDialog from '../components/ui/ConfirmDialog.jsx'
import EmptyState from '../components/ui/EmptyState.jsx'
import Skeleton from '../components/ui/Skeleton.jsx'
import './ReposPage.css'

// Hoisted static placeholder list
const SKELETON_ROWS = [0, 1, 2, 3]

function RepoSkeletons() {
  return (
    <div className="rp-list">
      {SKELETON_ROWS.map((i) => (
        <div key={i} className="rp-card rp-card-skel">
          <div className="rp-card-main">
            <Skeleton width="180px" height="18px" radius="6px" />
            <Skeleton width="240px" height="12px" radius="4px" />
          </div>
          <div className="rp-card-actions">
            <Skeleton width="96px" height="32px" radius="6px" />
            <Skeleton width="96px" height="32px" radius="6px" />
          </div>
        </div>
      ))}
    </div>
  )
}

function ReposPage() {
  const navigate = useNavigate()
  const [repos, setRepos] = useState([])
  const [username, setUsername] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [pendingRepo, setPendingRepo] = useState(null)
  const [confirmConfig, setConfirmConfig] = useState(null)
  const [toast, setToast] = useState(null)
  const toastTimer = useRef(null)

  const showToast = useCallback((message, type = 'error') => {
    clearTimeout(toastTimer.current)
    setToast({ message, type })
    toastTimer.current = setTimeout(() => setToast(null), 4000)
  }, [])

  useEffect(() => () => clearTimeout(toastTimer.current), [])

  const fetchRepos = useCallback(() => {
    fetch('/api/repos', { credentials: 'include' })
      .then((res) => {
        if (res.status === 401) { navigate('/'); return null }
        if (!res.ok) throw new Error('Failed to fetch repositories')
        return res.json()
      })
      .then((data) => {
        if (!data) return
        setRepos(data.repos)
        setUsername(data.username)
        setError(null)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [navigate])

  useEffect(() => { fetchRepos() }, [fetchRepos])

  const refresh = useCallback(() => { setLoading(true); fetchRepos() }, [fetchRepos])

  // Shared POST helper for the activate / deactivate / delete-data endpoints.
  const mutate = (repoFullName, action, onData) => {
    setPendingRepo(repoFullName)
    fetch(`/api/repos/${action}?repo_full_name=${encodeURIComponent(repoFullName)}`, {
      method: 'POST',
      credentials: 'include',
    })
      .then((res) => res.json())
      .then(onData)
      .catch((err) => showToast(err.message, 'error'))
      .finally(() => setPendingRepo(null))
  }

  const handleActivate = (repo) =>
    mutate(repo, 'activate', (data) => {
      if (data.status === 'activated') fetchRepos()
      else showToast(data.error || 'Activation failed', 'error')
    })

  const doDeactivate = (repo) =>
    mutate(repo, 'deactivate', (data) => {
      if (data.status === 'deactivated') fetchRepos()
      else showToast(data.error || 'Deactivation failed', 'error')
    })

  const doDelete = (repo) =>
    mutate(repo, 'delete-data', (data) => {
      if (data.status === 'deleted') {
        showToast(
          `Deleted ${data.deleted_docs} docs and ${data.deleted_registry} registry entries.`,
          'success',
        )
      } else {
        showToast(data.error || 'Delete failed', 'error')
      }
    })

  const askDeactivate = (repo) =>
    setConfirmConfig({
      title: 'Deactivate repository',
      message: `Deactivate ${repo}? This removes the webhook, but existing documentation data will remain.`,
      confirmLabel: 'Deactivate',
      danger: false,
      onConfirm: () => { setConfirmConfig(null); doDeactivate(repo) },
    })

  const askDelete = (repo) =>
    setConfirmConfig({
      title: 'Delete documentation data',
      message: `Permanently delete all documentation data for ${repo}? This cannot be undone.`,
      confirmLabel: 'Delete data',
      danger: true,
      onConfirm: () => { setConfirmConfig(null); doDelete(repo) },
    })

  const handleLogout = () => {
    fetch('/api/auth/logout', { method: 'POST', credentials: 'include' }).finally(() => navigate('/'))
  }

  return (
    <div className="repos-page">
      <header className="rp-header">
        <div className="rp-header-title">
          {loading ? (
            <Skeleton width="150px" height="20px" radius="6px" />
          ) : (
            <>
              <h1>{username ? `${username}'s repositories` : 'Repositories'}</h1>
              <span className="rp-header-count">{repos.length}</span>
            </>
          )}
        </div>
        <Button variant="ghost" size="sm" onClick={handleLogout}>Log out</Button>
      </header>

      <div className="rp-container">
        {loading && <RepoSkeletons />}

        {!loading && error && (
          <EmptyState
            title="Something went wrong"
            message={error}
            action={<Button variant="ghost" size="sm" onClick={refresh}>Try again</Button>}
          />
        )}

        {!loading && !error && repos.length === 0 && (
          <EmptyState
            title="No repositories yet"
            message="We couldn't find any repositories for your account. Make sure the GitHub App has access, then refresh."
            action={<Button variant="ghost" size="sm" onClick={refresh}>Refresh</Button>}
          />
        )}

        {!loading && !error && repos.length > 0 && (
          <div className="rp-list">
            {repos.map((repo) => {
              const busy = pendingRepo === repo.full_name
              return (
                <div key={repo.full_name} className="rp-card">
                  <div className="rp-card-main">
                    <div className="rp-card-name-row">
                      <Link to={`/repos/${repo.full_name}`} className="rp-card-name">
                        {repo.name}
                      </Link>
                      {repo.private && <span className="rp-lock" title="Private">🔒</span>}
                      <span className={`rp-status ${repo.is_active ? 'active' : 'inactive'}`}>
                        <span className="rp-status-dot" />
                        {repo.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    <div className="rp-card-full">{repo.full_name}</div>
                  </div>

                  <div className="rp-card-actions">
                    {repo.is_active ? (
                      <Button variant="ghost" size="sm" disabled={busy}
                        onClick={() => askDeactivate(repo.full_name)}>
                        Deactivate
                      </Button>
                    ) : (
                      <Button variant="primary" size="sm" disabled={busy}
                        onClick={() => handleActivate(repo.full_name)}>
                        Activate
                      </Button>
                    )}
                    <Button variant="danger" size="sm" disabled={busy}
                      onClick={() => askDelete(repo.full_name)}>
                      Delete data
                    </Button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {toast && (
        <div className={`rp-toast ${toast.type}`} role="status">
          <span className={`rp-toast-icon ${toast.type}`}>
            {toast.type === 'success' ? '✓' : '!'}
          </span>
          <span className="rp-toast-msg">{toast.message}</span>
          <button className="rp-toast-close" onClick={() => setToast(null)} aria-label="Dismiss">×</button>
        </div>
      )}

      <ConfirmDialog
        open={!!confirmConfig}
        title={confirmConfig?.title}
        message={confirmConfig?.message}
        confirmLabel={confirmConfig?.confirmLabel}
        danger={confirmConfig?.danger}
        onConfirm={confirmConfig?.onConfirm}
        onCancel={() => setConfirmConfig(null)}
      />
    </div>
  )
}

export default ReposPage
