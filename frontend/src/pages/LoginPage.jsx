import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Button from '../components/ui/Button.jsx'
import Skeleton from '../components/ui/Skeleton.jsx'
import './LoginPage.css'

// Hoisted so they aren't rebuilt on every render (rendering-hoist-jsx).
const LOGIN_LOGO = (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5" />
    <path d="M9 13h6" />
    <path d="M9 17h4" />
  </svg>
)

const GITHUB_ICON = (
  <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
    <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.6 7.6 0 0 1 2-.27c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
  </svg>
)

function LoginPage() {
  const navigate = useNavigate()
  // Start in a "checking" state so we never flash the login card before we
  // know whether an existing session should redirect straight to /repos.
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    let cancelled = false
    fetch('/api/auth/me', { credentials: 'include' })
      .then((res) => {
        if (cancelled) return
        if (res.ok) navigate('/repos')
        else setChecking(false)
      })
      .catch(() => { if (!cancelled) setChecking(false) })
    return () => { cancelled = true }
  }, [navigate])

  function handleLogin() {
    window.location.href = '/api/auth/login'
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">{LOGIN_LOGO}</div>

        {checking ? (
          <div className="login-skel">
            <Skeleton width="180px" height="26px" radius="7px" />
            <Skeleton width="240px" height="15px" radius="5px" />
            <Skeleton width="100%" height="42px" radius="8px" />
          </div>
        ) : (
          <>
            <h1 className="login-title">AI Autodoc Service</h1>
            <p className="login-subtitle">
              Automatic, always-up-to-date documentation for your GitHub repositories.
            </p>
            <Button variant="primary" size="md" className="login-btn" onClick={handleLogin}>
              {GITHUB_ICON}
              Continue with GitHub
            </Button>
            <p className="login-footer">Signing in grants access to all of your GitHub repositories.</p>
          </>
        )}
      </div>
    </div>
  )
}

export default LoginPage
