import React, { useEffect, useMemo, useRef } from 'react'

// Fixed newsroom roster, in pipeline order. Keys must match backend agent ids.
const ROSTER = [
  { key: 'orchestrator', name: 'Editor-in-Chief', role: 'Plans & routes the story', glyph: 'star' },
  { key: 'ingestor', name: 'Ingestor', role: 'Fetches & scrapes sources', glyph: 'press' },
  { key: 'researcher', name: 'Researcher', role: 'Widens the source net', glyph: 'lens' },
  { key: 'clustering', name: 'Story Clusterer', role: 'Groups the same event (DBSCAN)', glyph: 'nodes' },
  { key: 'fact_checker', name: 'Fact-Checker', role: 'Verifies claims across sources', glyph: 'check' },
  { key: 'bias_auditor', name: 'Bias Auditor', role: 'Weights & scores the Bias Index', glyph: 'scale' },
  { key: 'editor', name: 'Copy Editor', role: 'Files the finished report', glyph: 'pen' },
]

function Glyph({ name }) {
  const common = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round' }
  switch (name) {
    case 'star':
      return <svg viewBox="0 0 24 24" className="w-6 h-6"><path {...common} d="M12 3l2.4 5.3 5.8.6-4.3 3.9 1.2 5.7L12 17.6 6.9 21.4l1.2-5.7L3.8 11.9l5.8-.6L12 3z" /></svg>
    case 'press':
      return <svg viewBox="0 0 24 24" className="w-6 h-6"><rect {...common} x="3" y="4" width="18" height="16" rx="1" /><path {...common} d="M7 8h6M7 12h10M7 16h10" /></svg>
    case 'lens':
      return <svg viewBox="0 0 24 24" className="w-6 h-6"><circle {...common} cx="11" cy="11" r="6" /><path {...common} d="M20 20l-4.5-4.5" /></svg>
    case 'nodes':
      return <svg viewBox="0 0 24 24" className="w-6 h-6"><circle {...common} cx="6" cy="7" r="2.2" /><circle {...common} cx="18" cy="6" r="2.2" /><circle {...common} cx="12" cy="17" r="2.2" /><path {...common} d="M7.7 8.6l3.3 6.3M16.4 7.6L13 15" /></svg>
    case 'check':
      return <svg viewBox="0 0 24 24" className="w-6 h-6"><path {...common} d="M4 12.5l4.5 4.5L20 6" /></svg>
    case 'scale':
      return <svg viewBox="0 0 24 24" className="w-6 h-6"><path {...common} d="M12 3v17M5 20h14M4 8h16M4 8l-2 5a3 3 0 006 0L6 8M20 8l-2 5a3 3 0 006 0l-2-5" /></svg>
    case 'pen':
      return <svg viewBox="0 0 24 24" className="w-6 h-6"><path {...common} d="M4 20l4-1L20 7a2 2 0 00-3-3L5 16l-1 4zM14 6l3 3" /></svg>
    default:
      return null
  }
}

function StatusLight({ state }) {
  if (state === 'done') {
    return <span className="text-ink text-lg leading-none" title="Done">✓</span>
  }
  if (state === 'error') {
    return <span className="text-stamp text-lg leading-none" title="Error">✕</span>
  }
  if (state === 'active') {
    return <span className="inline-block w-2.5 h-2.5 rounded-full bg-ink animate-blink" title="Working" />
  }
  return <span className="inline-block w-2.5 h-2.5 rounded-full border border-ink-faint" title="Idle" />
}

function deriveStates(events, finished) {
  const latest = {}
  let activeKey = null
  for (const e of events) {
    if (e.type !== 'agent') continue
    latest[e.agent] = e
    if (e.status !== 'done' && e.status !== 'error') activeKey = e.agent
    else if (e.agent === activeKey) activeKey = null
  }
  const states = {}
  for (const { key } of ROSTER) {
    const e = latest[key]
    if (!e) { states[key] = { state: 'idle', detail: '', data: {} }; continue }
    let state = 'active'
    if (e.status === 'done') state = 'done'
    else if (e.status === 'error') state = 'error'
    else if (finished) state = 'done'
    else if (key === activeKey) state = 'active'
    else state = 'done' // touched earlier, moved on
    states[key] = { state, detail: e.detail || e.title, data: e.data || {} }
  }
  return { states, activeKey: finished ? null : activeKey }
}

function chipsFor(data) {
  const out = []
  if (data.articles != null) out.push(`${data.articles} art.`)
  if (data.sources != null) out.push(`${data.sources} src`)
  if (data.clusters != null) out.push(`${data.clusters} clusters`)
  if (data.facts_supported != null) out.push(`${data.facts_supported}✓`)
  if (data.facts_contradicted != null) out.push(`${data.facts_contradicted}✕`)
  if (data.news_category) out.push(data.news_category)
  return out.slice(0, 3)
}

function AgentPipeline({ events, finished }) {
  const { states } = useMemo(() => deriveStates(events, finished), [events, finished])
  const consoleRef = useRef(null)
  const agentEvents = useMemo(() => events.filter((e) => e.type === 'agent'), [events])

  useEffect(() => {
    if (consoleRef.current) consoleRef.current.scrollTop = consoleRef.current.scrollHeight
  }, [agentEvents.length])

  return (
    <div className="card p-5 sm:p-6">
      <div className="flex items-baseline justify-between border-b border-ink pb-2 mb-4">
        <h3 className="headline text-2xl">The Newsroom</h3>
        <span className="kicker">Live Wire · Agentic Pipeline</span>
      </div>

      {/* Agent desks */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3">
        {ROSTER.map((agent, idx) => {
          const s = states[agent.key]
          const isActive = s.state === 'active'
          return (
            <div key={agent.key} className="relative">
              <div
                className={`card-flat h-full p-3 flex flex-col gap-2 transition-all ${
                  isActive ? 'bg-ink text-paper animate-pulse-ring' : ''
                } ${s.state === 'idle' ? 'opacity-45' : ''}`}
              >
                <div className="flex items-center justify-between">
                  <div className={isActive ? 'text-paper' : 'text-ink'}>
                    <Glyph name={agent.glyph} />
                  </div>
                  <div className={isActive ? 'text-paper' : ''}>
                    <StatusLight state={s.state} />
                  </div>
                </div>
                <div>
                  <p className={`font-display font-bold leading-tight text-sm ${isActive ? 'text-paper' : 'text-ink'}`}>
                    {agent.name}
                  </p>
                  <p className={`text-[10px] leading-tight mt-0.5 ${isActive ? 'text-paper/80' : 'text-ink-faint'}`}>
                    {agent.role}
                  </p>
                </div>
                {s.detail && (
                  <p className={`text-[10.5px] leading-snug font-serif ${isActive ? 'text-paper/90' : 'text-ink-soft'}`}>
                    {s.detail.length > 74 ? s.detail.slice(0, 74) + '…' : s.detail}
                  </p>
                )}
                {chipsFor(s.data).length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-auto pt-1">
                    {chipsFor(s.data).map((c, i) => (
                      <span
                        key={i}
                        className={`px-1.5 py-0.5 text-[9px] font-mono border ${
                          isActive ? 'border-paper/60 text-paper' : 'border-ink-faint text-ink-soft'
                        }`}
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              {idx < ROSTER.length - 1 && (
                <span className="hidden lg:block absolute top-1/2 -right-2.5 -translate-y-1/2 text-ink-faint z-10">→</span>
              )}
            </div>
          )
        })}
      </div>

      {/* Live wire console */}
      <div className="mt-5">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="kicker">Wire Feed</span>
          <span className="flex-1 rule-thin border-ink/40" />
        </div>
        <div
          ref={consoleRef}
          className="bg-ink text-paper font-mono text-xs p-3 h-44 overflow-y-auto leading-relaxed"
        >
          {agentEvents.length === 0 && (
            <p className="opacity-60">— awaiting dispatch from the desk —</p>
          )}
          {agentEvents.map((e, i) => (
            <div key={i} className="whitespace-pre-wrap">
              <span className="opacity-50">{formatTs(e.ts)} </span>
              <span className="text-paper font-semibold">[{e.agent_name}]</span>{' '}
              <span className={e.status === 'error' ? 'text-red-300' : 'opacity-90'}>
                {e.title}
                {e.detail ? ` — ${e.detail}` : ''}
              </span>
            </div>
          ))}
          {!finished && agentEvents.length > 0 && (
            <span className="inline-block w-2 h-4 bg-paper align-middle animate-blink" />
          )}
        </div>
      </div>
    </div>
  )
}

function formatTs(ts) {
  if (!ts) return '--:--:--'
  try {
    return new Date(ts).toLocaleTimeString('en-GB', { hour12: false })
  } catch {
    return '--:--:--'
  }
}

export default AgentPipeline
