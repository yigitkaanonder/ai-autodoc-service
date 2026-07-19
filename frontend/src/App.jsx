import { Routes, Route } from 'react-router-dom'
import LoginPage from './pages/LoginPage.jsx'
import ReposPage from './pages/ReposPage.jsx'
import RepoDetailPage from './pages/RepoDetailPage.jsx'
import DocsPage from './pages/DocsPage.jsx'

function App() {
  return (
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route path="/repos" element={<ReposPage />} />
      <Route path="/repos/:owner/:name" element={<RepoDetailPage />} />
      <Route path="/repos/:owner/:name/docs" element={<DocsPage />} />
    </Routes>
  )
}

export default App