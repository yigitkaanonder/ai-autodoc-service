import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
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
  const [documentedHeadSha, setDocumentedHeadSha] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedSha, setSelectedSha] = useState(null)
  const [live, setLive] = useState(false)   // SSE connected?
  const [flash, setFlash] = useState(false)  // brief highlight on update
  const flashTimer = useRef(null)

  // changes for the selected commit
  const [changes, setChanges] = useState(null)
  const [changesLoading, setChangesLoading] = useState(false)
  const [expandedDocId, setExpandedDocId] = useState(null)

  // full snapshot overlay
  const [snapshotOpen, setSnapshotOpen] = useState(false)
  const [snapshot, setSnapshot] = useState(null)
  const [snapshotLoading, setSnapshotLoading] = useState(false)

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
        setDocumentedHeadSha(data.documented_head_sha || null)
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

    // ---- fetch changes when a commit is selected ----
  useEffect(() => {
    if (!selectedSha) { setChanges(null); return }
    setChangesLoading(true)
    setExpandedDocId(null)
    fetch(`/api/repos/${owner}/${name}/commits/${selectedSha}/changes`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setChanges(data))
      .catch(() => setChanges(null))
      .finally(() => setChangesLoading(false))
  }, [selectedSha, owner, name])

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

  // documented commits = the high-water-mark commit and all its ancestors
  const documentedSet = useMemo(() => {
    const set = new Set()
    if (!documentedHeadSha) return set
    const parentsBySha = {}
    commits.forEach((c) => { parentsBySha[c.sha] = c.parents || [] })
    const stack = [documentedHeadSha]
    while (stack.length) {
      const sha = stack.pop()
      if (set.has(sha)) continue
      set.add(sha)
      for (const p of (parentsBySha[sha] || [])) stack.push(p)
    }
    return set
  }, [documentedHeadSha, commits])

  const selected = commits.find((c) => c.sha === selectedSha) || null
  const selectedDocumented = selected ? documentedSet.has(selected.sha) : false

  const openSnapshot = () => {
    if (!selectedSha) return
    const username = localStorage.getItem('username')
    setSnapshotOpen(true)
    setSnapshot(null)
    setSnapshotLoading(true)
    fetch(`/api/repos/${owner}/${name}/commits/${selectedSha}/snapshot?username=${username}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setSnapshot(data))
      .catch(() => setSnapshot(null))
      .finally(() => setSnapshotLoading(false))
  }

  const x = (col) => GUTTER + col * COL_WIDTH
  const y = (row) => row * ROW_HEIGHT + ROW_HEIGHT / 2
  const graphWidth = Math.max(GUTTER * 2 + maxColumn * COL_WIDTH, 56)

  if (loading) return <div className="repo-graph"><div className="rg-state">Loading commit graph...</div></div>
  if (error) return <div className="repo-graph"><div className="rg-state">Error: {error}</div></div>

    const renderChangeItem = (item, kind) => {
      const isOpen = expandedDocId === item.id
      return (
        <div key={`${kind}-${item.id}`} className="rg-change-item">
          <div className="rg-change-head" onClick={() => setExpandedDocId(isOpen ? null : item.id)}>
            <span className="rg-change-fn">{item.function_name}</span>
            <span className="rg-change-file">{item.file_path}</span>
            <span className="rg-change-toggle">{isOpen ? '−' : '+'}</span>
          </div>
          {isOpen && (
            <div className="rg-doc-content">
              <ReactMarkdown>{item.content || ''}</ReactMarkdown>
            </div>
          )}
        </div>
      )
    }
  
    return (
      <div className="repo-graph">
        <div className="rg-header">
          <button className="rg-back" onClick={() => navigate('/repos')}>← Repos</button>
          <div>
            <h1 className="rg-title">{owner}/{name}</h1>
            <div className="rg-subtitle">{commits.length} commits · {branches.length} branches</div>
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
            <svg className="rg-graph-svg" width={graphWidth} height={commits.length * ROW_HEIGHT}>
              {displayCommits.map((commit, i) => {
                const cx = x(columnBySha[commit.sha])
                const cy = y(i)
                return (commit.parents || []).map((parentSha) => {
                  const pRow = rowBySha[parentSha]
                  if (pRow === undefined) return null
                  const px = x(columnBySha[parentSha])
                  const py = y(pRow)
                  const color = laneColor(columnBySha[commit.sha])
                  const midY = (cy + py) / 2
                  const d = `M ${cx} ${cy} C ${cx} ${midY}, ${px} ${midY}, ${px} ${py}`
                  return (
                    <path key={`${commit.sha}-${parentSha}`} d={d}
                      stroke={color} strokeWidth="2" fill="none" opacity="0.75" />
                  )
                })
              })}
  
              {displayCommits.map((commit, i) => {
                const cx = x(columnBySha[commit.sha])
                const cy = y(i)
                const color = laneColor(columnBySha[commit.sha])
                const isSelected = commit.sha === selectedSha
                const isDocumented = documentedSet.has(commit.sha)
                return (
                  <g key={commit.sha} opacity={isDocumented ? 1 : 0.4}>
                    {isDocumented && (
                      <circle cx={cx} cy={cy} r={NODE_R + 3} fill="none"
                        stroke="#3fb950" strokeWidth="1.5" opacity="0.6" />
                    )}
                    <circle
                      className={`commit-node ${isSelected ? 'selected' : ''}`}
                      cx={cx} cy={cy} r={NODE_R}
                      fill={commit.is_merge ? 'var(--rg-bg)' : color}
                      stroke={color}
                      strokeWidth={commit.is_merge ? 2.5 : 1.5}
                      onClick={() => setSelectedSha(commit.sha)}
                    />
                  </g>
                )
              })}
            </svg>
  
            {displayCommits.map((commit, i) => {
              const isDocumented = documentedSet.has(commit.sha)
              return (
                <div
                  key={commit.sha}
                  className={`rg-row ${commit.sha === selectedSha ? 'selected' : ''}`}
                  style={{ height: ROW_HEIGHT, opacity: isDocumented ? 1 : 0.55 }}
                  onClick={() => setSelectedSha(commit.sha)}
                >
                  <div style={{ width: graphWidth, flexShrink: 0 }} />
                  <div className="rg-cell rg-cell-msg">
                    {isDocumented && <span className="rg-doc-dot" title="Documented" />}
                    <span className="msg-text">{commit.message}</span>
                    {(headBranches[commit.sha] || []).map((branchName) => {
                      const color = laneColor(columnBySha[commit.sha])
                      return (
                        <span key={branchName} className="rg-chip" style={{ color, borderColor: color }}>
                          {branchName}
                        </span>
                      )
                    })}
                  </div>
                  <div className="rg-cell rg-cell-sha">{commit.short_sha}</div>
                  <div className="rg-cell rg-cell-author">{commit.author}</div>
                  <div className="rg-cell rg-cell-date">{(commit.date || '').slice(0, 10)}</div>
                </div>
              )
            })}
  
            {commits.length === 0 && <div className="rg-state">No commits found for this repository.</div>}
          </div>
        </div>
  
        {selected && (
          <div className="rg-detail">
            <div className="rg-detail-head">
              <div className="rg-avatar">{(selected.author || '?').charAt(0).toUpperCase()}</div>
              <div style={{ flex: 1 }}>
                <h3 className="rg-detail-msg">{selected.message}</h3>
                <div className="rg-detail-meta">
                  <span><strong style={{ color: 'var(--rg-text)' }}>{selected.author}</strong> · {(selected.date || '').slice(0, 10)}</span>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>{selected.short_sha}</span>
                  {selected.is_merge && <span style={{ color: 'var(--rg-primary)' }}>merge</span>}
                </div>
              </div>
              {selectedDocumented
                ? <button className="rg-snapshot-btn" onClick={openSnapshot}>View full documentation here</button>
                : <span className="rg-not-documented">Not documented</span>}
            </div>
  
            {selectedDocumented && (
              <div className="rg-changes">
                {changesLoading && <div className="rg-changes-empty">Loading changes…</div>}
                {!changesLoading && changes &&
                  ((changes.added.length + changes.changed.length + changes.deleted.length) === 0
                    ? <div className="rg-changes-empty">No documentation changes at this commit (state carried forward).</div>
                    : (
                      <>
                        {changes.added.length > 0 && (
                          <div className="rg-change-group">
                            <div className="rg-change-label rg-added">Added ({changes.added.length})</div>
                            {changes.added.map((it) => renderChangeItem(it, 'added'))}
                          </div>
                        )}
                        {changes.changed.length > 0 && (
                          <div className="rg-change-group">
                            <div className="rg-change-label rg-changed">Changed ({changes.changed.length})</div>
                            {changes.changed.map((it) => renderChangeItem(it, 'changed'))}
                          </div>
                        )}
                        {changes.deleted.length > 0 && (
                          <div className="rg-change-group">
                            <div className="rg-change-label rg-deleted">Deleted ({changes.deleted.length})</div>
                            {changes.deleted.map((it, idx) => (
                              <div key={`del-${idx}`} className="rg-change-item">
                                <div className="rg-change-head static">
                                  <span className="rg-change-fn">{it.function_name}</span>
                                  <span className="rg-change-file">{it.file_path}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </>
                    ))}
              </div>
            )}
          </div>
        )}
  
        {snapshotOpen && (
          <div className="rg-overlay" onClick={() => setSnapshotOpen(false)}>
            <div className="rg-modal" onClick={(e) => e.stopPropagation()}>
              <div className="rg-modal-head">
                <div>
                  <div className="rg-modal-title">Documentation snapshot</div>
                  <div className="rg-modal-sub">as of {selected ? selected.short_sha : ''}</div>
                </div>
                <button className="rg-modal-close" onClick={() => setSnapshotOpen(false)}>×</button>
              </div>
              <div className="rg-modal-body">
                {snapshotLoading && <div className="rg-changes-empty">Loading snapshot…</div>}
                {!snapshotLoading && snapshot && snapshot.docs.length === 0 &&
                  <div className="rg-changes-empty">No documentation at this commit.</div>}
                {!snapshotLoading && snapshot && snapshot.docs.map((doc) => (
                  <div key={doc.id} className="rg-doc-card">
                    <div className="rg-doc-card-head">
                      <span className="rg-change-fn">{doc.function_name}</span>
                      <span className="rg-change-file">{doc.file_path}</span>
                    </div>
                    <div className="rg-doc-content">
                      <ReactMarkdown>{doc.content || ''}</ReactMarkdown>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }
  
  export default RepoDetailPage