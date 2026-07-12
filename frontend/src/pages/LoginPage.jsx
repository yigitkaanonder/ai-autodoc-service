import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

function LoginPage() {
  const navigate = useNavigate()

  // If a valid session cookie already exists, skip straight to /repos.
  // The cookie is HttpOnly so JS can't read it directly — we ask the server.
  useEffect(() => {
    fetch('/api/auth/me', { credentials: 'include' })
      .then((res) => { if (res.ok) navigate('/repos') })
      .catch(() => {})
  }, [navigate])

  function handleLogin() {
    window.location.href = '/api/auth/login'
  }

  return (
    <div style={{ textAlign: 'center', marginTop: '100px' }}>
      <h1>AI Autodoc Service</h1>
      <p>Generate documentation for your GitHub repos automatically.</p>
      <button onClick={handleLogin} style={{ padding: '12px 24px', fontSize: '16px', cursor: 'pointer' }}>
        Login with GitHub
      </button>
    </div>
  )
}

export default LoginPage
