import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  useEffect(() => {
    // OAuth callback'ten döndüyse URL'de username olur
    const username = searchParams.get('username')
    if (username) {
      // username'i kaydet ve repos sayfasına git
      localStorage.setItem('username', username)
      navigate('/repos')
    }
  }, [searchParams, navigate])

  // Daha önce giriş yapmışsa direkt yönlendir
  useEffect(() => {
    const saved = localStorage.getItem('username')
    if (saved) {
      navigate('/repos')
    }
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