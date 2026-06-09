import { Routes, Route } from 'react-router-dom'
import LoginPage from './pages/LoginPage.jsx'
import ReposPage from './pages/ReposPage.jsx'
import RepoDetailPage from './pages/RepoDetailPage.jsx'

function App() {
  return (
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route path="/repos" element={<ReposPage />} />
      <Route path="/repos/:owner/:name" element={<RepoDetailPage />} />
    </Routes>
  )
}

export default App