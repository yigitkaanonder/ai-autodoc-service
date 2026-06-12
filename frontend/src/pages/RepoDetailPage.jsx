import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import './RepoDetailPage.css'

// ---- layout constants (tweak these to change graph density) ----
const ROW_HEIGHT = 44
const COL_WIDTH = 22
const GUTTER = 18
const NODE_R = 5

// Lane colors cycle by column index.
const LANE_COLORS = [
  '#58a6ff', '#3fb950', '#ffba42', '#e879f9',
  '#ff7b72', '#a5d6ff', '#bc8cff', '#ffa657',
]
const laneColor = (col) => LANE_COLORS[col % LANE_COLORS.length]

/**
 * Assign each commit to a vertical lane (column). 
 * We walk commits newest -> oldest and keep a list
 * of "active lanes". Each lane is reserved for the sha it expects next.
 *
 *  - A commit takes the lane a child reserved for it; if none exists it
 *    is a branch tip and gets a fresh lane.
 *  - Its first parent continues in the same lane (a straight line down).
 *  - Extra parents (merge commits) open new lanes.
 *  - When several lanes are reserved for the same commit, they converge
 *    into the leftmost one (that's a merge point).
 *
 * Returns columnBySha and the max column used (graph width).
 */
function assignLanes(commits) {
  const columnBySha = {}
  const lanes = [] // lanes[i] = sha this lane is waiting for, or null

  const reserveLane = (sha) => {
    for (let i = 0; i < lanes.length; i++) {
      if (lanes[i] === null) { lanes[i] = sha; return i }
    }
    lanes.push(sha)
    return lanes.length - 1
  }

  for (const commit of commits) {
    let col = lanes.indexOf(commit.sha)
    if (col === -1) {
      col = reserveLane(commit.sha) // branch tip with no visible child
    } else {
      // free any other lanes reserved for this same sha -> they merge in
      for (let i = 0; i < lanes.length; i++) {
        if (i !== col && lanes[i] === commit.sha) lanes[i] = null
      }
    }
    columnBySha[commit.sha] = col

    const parents = commit.parents || []
    if (parents.length === 0) {
      lanes[col] = null // root commit: lane ends here
    } else {
      lanes[col] = parents[0] // first parent stays in this lane
      for (let p = 1; p < parents.length; p++) {
        if (!lanes.includes(parents[p])) reserveLane(parents[p])
      }
    }
  }

  let maxColumn = 0
  for (const sha in columnBySha) maxColumn = Math.max(maxColumn, columnBySha[sha])
  return { columnBySha, maxColumn }
}

function RepoDetailPage() {
  const { owner, name } = useParams()
  const navigate = useNavigate()

  const [commits, setCommits] = useState([])
  const [branches, setBranches] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedSha, setSelectedSha] = useState(null)
  const [live, setLive] = useState(false)   // SSE connected?
  const [flash, setFlash] = useState(false)  // brief highlight on update
  const flashTimer = useRef(null)

  // ---- fetch the commit graph from the backend ----
  const fetchGraph = useCallback(() => {
    // token is resolved from the logged-in user, so the graph works even
    // for repos that haven't been activated yet.
    const username = localStorage.getItem('username')
    return fetch(`/api/repos/${owner}/${name}/commits?username=${username}`)
      .then((res) => {
        if (!res.ok) throw new Error('Failed to fetch commit graph')
        return res.json()
      })
      .then((data) => {
        setBranches(data.branches || [])
        setCommits(data.commits || [])
        setError(null)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [owner, name])

  // initial load
  useEffect(() => { fetchGraph() }, [fetchGraph])

  // ---- live updates over SSE ----
  useEffect(() => {
    const es = new EventSource(`/api/repos/${owner}/${name}/events`)
    es.onopen = () => setLive(true)
    es.onerror = () => setLive(false) // browser auto-reconnects
    es.addEventListener('push', () => {
      fetchGraph()
      setFlash(true)
      clearTimeout(flashTimer.current)
      flashTimer.current = setTimeout(() => setFlash(false), 1500)
    })
    return () => {
      es.close()
      clearTimeout(flashTimer.current)
    }
  }, [owner, name, fetchGraph])

  // ---- derived data ----
  // The lane algorithm needs newest-first order (a commit's parents always
  // come later in the list). For display we reverse it so the timeline flows
  // downward: oldest at the top, newest at the bottom.
  const { columnBySha, maxColumn } = useMemo(() => assignLanes(commits), [commits])

  const displayCommits = useMemo(() => [...commits].reverse(), [commits])

  const rowBySha = useMemo(() => {
    const map = {}
    displayCommits.forEach((c, i) => { map[c.sha] = i })
    return map
  }, [displayCommits])

  // sha -> [branch names whose head is this commit]
  const headBranches = useMemo(() => {
    const map = {}
    for (const b of branches) {
      (map[b.head_sha] = map[b.head_sha] || []).push(b.name)
    }
    return map
  }, [branches])

  const selected = commits.find((c) => c.sha === selectedSha) || null

  const x = (col) => GUTTER + col * COL_WIDTH
  const y = (row) => row * ROW_HEIGHT + ROW_HEIGHT / 2
  const graphWidth = Math.max(GUTTER * 2 + maxColumn * COL_WIDTH, 56)

  if (loading) return <div className="repo-graph"><div className="rg-state">Loading commit graph...</div></div>
  if (error) return <div className="repo-graph"><div className="rg-state">Error: {error}</div></div>

  return (
    <div className="repo-graph">
      <div className="rg-header">
        <button className="rg-back" onClick={() => navigate('/repos')}>← Repos</button>
        <div>
          <h1 className="rg-title">{owner}/{name}</h1>
          <div className="rg-subtitle">
            {commits.length} commits · {branches.length} branches
          </div>
        </div>
        <div className="rg-spacer" />
        <div className={`rg-live ${live ? '' : 'offline'} ${flash ? 'flash' : ''}`}>
          <span className="rg-live-dot" />
          {flash ? 'Updated' : live ? 'Live' : 'Reconnecting'}
        </div>
      </div>

      <div className="rg-table">
        <div className="rg-thead">
          <div style={{ width: graphWidth }}>Graph</div>
          <div style={{ flex: 1 }}>Description</div>
          <div className="rg-cell-sha">Commit</div>
          <div className="rg-cell-author">Author</div>
          <div className="rg-cell-date">Date</div>
        </div>

        <div className="rg-body" style={{ height: commits.length * ROW_HEIGHT }}>
          {/* SVG layer: lines first, then nodes */}
          <svg
            className="rg-graph-svg"
            width={graphWidth}
            height={commits.length * ROW_HEIGHT}
          >
            {displayCommits.map((commit, i) => {
              const cx = x(columnBySha[commit.sha])
              const cy = y(i)
              return (commit.parents || []).map((parentSha) => {
                const pRow = rowBySha[parentSha]
                if (pRow === undefined) return null // parent outside loaded range
                const px = x(columnBySha[parentSha])
                const py = y(pRow)
                const color = laneColor(columnBySha[commit.sha])
                // smooth S-curve that works whether the parent is above or below
                const midY = (cy + py) / 2
                const d = `M ${cx} ${cy} C ${cx} ${midY}, ${px} ${midY}, ${px} ${py}`
                return (
                  <path
                    key={`${commit.sha}-${parentSha}`}
                    d={d}
                    stroke={color}
                    strokeWidth="2"
                    fill="none"
                    opacity="0.75"
                  />
                )
              })
            })}

            {displayCommits.map((commit, i) => {
              const cx = x(columnBySha[commit.sha])
              const cy = y(i)
              const color = laneColor(columnBySha[commit.sha])
              const isSelected = commit.sha === selectedSha
              return (
                <circle
                  key={commit.sha}
                  className={`commit-node ${isSelected ? 'selected' : ''}`}
                  cx={cx}
                  cy={cy}
                  r={NODE_R}
                  fill={commit.is_merge ? 'var(--rg-bg)' : color}
                  stroke={color}
                  strokeWidth={commit.is_merge ? 2.5 : 1.5}
                  onClick={() => setSelectedSha(commit.sha)}
                />
              )
            })}
          </svg>

          {/* HTML rows on top */}
          {displayCommits.map((commit, i) => (
            <div
              key={commit.sha}
              className={`rg-row ${commit.sha === selectedSha ? 'selected' : ''}`}
              style={{ height: ROW_HEIGHT }}
              onClick={() => setSelectedSha(commit.sha)}
            >
              <div style={{ width: graphWidth, flexShrink: 0 }} />
              <div className="rg-cell rg-cell-msg">
                <span className="msg-text">{commit.message}</span>
                {(headBranches[commit.sha] || []).map((branchName) => {
                  const color = laneColor(columnBySha[commit.sha])
                  return (
                    <span
                      key={branchName}
                      className="rg-chip"
                      style={{ color, borderColor: color }}
                    >
                      {branchName}
                    </span>
                  )
                })}
              </div>
              <div className="rg-cell rg-cell-sha">{commit.short_sha}</div>
              <div className="rg-cell rg-cell-author">{commit.author}</div>
              <div className="rg-cell rg-cell-date">{(commit.date || '').slice(0, 10)}</div>
            </div>
          ))}

          {commits.length === 0 && (
            <div className="rg-state">No commits found for this repository.</div>
          )}
        </div>
      </div>

      {selected && (
        <div className="rg-detail">
          <div className="rg-detail-head">
            <div className="rg-avatar">{(selected.author || '?').charAt(0).toUpperCase()}</div>
            <div>
              <h3 className="rg-detail-msg">{selected.message}</h3>
              <div className="rg-detail-meta">
                <span><strong style={{ color: 'var(--rg-text)' }}>{selected.author}</strong> committed on {(selected.date || '').slice(0, 10)}</span>
                <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>{selected.short_sha}</span>
                {selected.is_merge && <span style={{ color: 'var(--rg-primary)' }}>merge commit</span>}
              </div>
            </div>
          </div>

          <div className="rg-detail-grid">
            <div className="rg-detail-card">
              <div className="rg-detail-label">Branches at this commit</div>
              {(headBranches[selected.sha] || []).length > 0
                ? (headBranches[selected.sha] || []).join(', ')
                : <span style={{ color: 'var(--rg-muted)' }}>—</span>}
            </div>
            <div className="rg-detail-card">
              <div className="rg-detail-label">Parents</div>
              {(selected.parents || []).length > 0
                ? selected.parents.map((p) => {
                    const pc = commits.find((c) => c.sha === p)
                    return (
                      <span key={p} className="rg-parent-link" onClick={() => setSelectedSha(p)}>
                        {p.slice(0, 7)}{pc ? ` — ${pc.message.slice(0, 30)}` : ''}
                      </span>
                    )
                  })
                : <span style={{ color: 'var(--rg-muted)' }}>Initial commit</span>}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default RepoDetailPage