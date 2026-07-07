import React from 'react'

const DEFAULT_WEIGHTS = { tone: 0.4, lexical: 0.25, omission: 0.2, consistency: 0.15 }

// Monochrome fill treatments so the four components are distinguishable in B&W.
const FILLS = {
  tone: { className: 'bg-ink', label: 'Tone deviation', hint: 'How far this source’s sentiment strays from the cluster average.' },
  lexical: { className: 'halftone', label: 'Lexical bias', hint: 'Density of loaded / emotive / prescriptive language.' },
  omission: { className: 'crosshatch', label: 'Omission', hint: 'Share of the cluster’s verified facts this source leaves out.' },
  consistency: { className: 'bg-[repeating-linear-gradient(45deg,#14110c_0_2px,transparent_2px_5px)]', label: 'Consistency', hint: 'Internal subjectivity & how it tracks the shared facts.' },
}

const ORDER = ['tone', 'lexical', 'omission', 'consistency']

function clamp01(v) {
  return Math.max(0, Math.min(1, v))
}

function BiasIndexExplainer({ articles = [], weights }) {
  const scored = articles.filter((a) => a.bias_index != null)
  if (scored.length === 0) {
    return <p className="font-serif text-sm text-ink-faint">No bias scores available for this cluster.</p>
  }

  const w = { ...DEFAULT_WEIGHTS, ...(weights || {}) }
  const wSum = ORDER.reduce((s, k) => s + (w[k] || 0), 0) || 1
  const wNorm = Object.fromEntries(ORDER.map((k) => [k, (w[k] || 0) / wSum]))

  const tones = scored.map((a) => a.tone_score || 0)
  const meanTone = tones.reduce((s, t) => s + t, 0) / tones.length

  // Aggregate by source (a source may have several articles in the cluster).
  const bySource = new Map()
  for (const a of scored) {
    const key = a.source || 'Unknown'
    if (!bySource.has(key)) bySource.set(key, [])
    bySource.get(key).push(a)
  }

  const avg = (arr, f) => arr.reduce((s, a) => s + f(a), 0) / arr.length

  const allRows = [...bySource.entries()]
    .map(([source, arts]) => {
      const comp = {
        tone: clamp01(avg(arts, (a) => Math.abs((a.tone_score || 0) - meanTone) / 2)),
        lexical: clamp01(avg(arts, (a) => a.lexical_bias_score || 0)),
        omission: clamp01(avg(arts, (a) => a.omission_score || 0)),
        consistency: clamp01(avg(arts, (a) => a.consistency_score || 0)),
      }
      const contrib = Object.fromEntries(ORDER.map((k) => [k, wNorm[k] * comp[k]]))
      return { source, index: avg(arts, (a) => a.bias_index || 0), count: arts.length, contrib }
    })
    .sort((x, y) => (y.index || 0) - (x.index || 0))

  // Keep the view scannable: most- and least-framed sources, not every row.
  const MAX_ROWS = 6
  const rows =
    allRows.length <= MAX_ROWS
      ? allRows
      : [...allRows.slice(0, MAX_ROWS - 2), ...allRows.slice(-2)]
  const hiddenCount = allRows.length - rows.length

  return (
    <div className="space-y-5">
      <p className="font-serif text-[15px] text-ink-soft leading-relaxed">
        The <span className="smallcaps font-bold">Bias Index</span> (0–100) measures how strongly a
        source <em>frames</em> a story rather than how “right” it is. It is a weighted blend of four
        measured signals. For this story the <span className="font-bold">Bias Auditor</span> agent set
        the weights below — heavier weight means that signal mattered more here.
      </p>

      {/* Weight allocation */}
      <div className="card-flat p-4">
        <p className="kicker mb-3">Auditor’s Weighting · Σ = 100%</p>
        <div className="flex h-6 border border-ink">
          {ORDER.map((k) => (
            <div
              key={k}
              className={`${FILLS[k].className} border-r border-ink last:border-r-0 flex items-center justify-center`}
              style={{ width: `${wNorm[k] * 100}%` }}
              title={`${FILLS[k].label}: ${Math.round(wNorm[k] * 100)}%`}
            />
          ))}
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3">
          {ORDER.map((k) => (
            <div key={k} className="flex items-center gap-2">
              <span className={`inline-block w-4 h-4 border border-ink ${FILLS[k].className}`} />
              <span className="text-xs font-mono">
                {FILLS[k].label} · {Math.round(wNorm[k] * 100)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Per-source contribution bars: most vs. least framed */}
      <div className="space-y-3">
        <p className="kicker">Most vs. least framed sources</p>
        {rows.map((r, i) => (
          <React.Fragment key={r.source}>
            {hiddenCount > 0 && i === rows.length - 2 && (
              <p className="dateline text-[11px] text-ink-faint text-center uppercase tracking-widest">
                ··· {hiddenCount} more source{hiddenCount === 1 ? '' : 's'} between ···
              </p>
            )}
            <div>
              <div className="flex justify-between items-baseline mb-1">
                <span className="font-display font-bold text-sm">
                  {r.source}
                  {r.count > 1 && (
                    <span className="font-mono font-normal text-[10px] text-ink-faint"> ×{r.count}</span>
                  )}
                </span>
                <span className="font-mono text-sm font-semibold">
                  {(r.index || 0).toFixed(0)}<span className="text-ink-faint">/100</span>
                </span>
              </div>
              <div className="h-5 border border-ink flex bg-[#fdfcf7]">
                {ORDER.map((k) => {
                  // width relative to the max possible magnitude (÷1.3 as in the model)
                  const pct = (r.contrib[k] / 1.3) * 100
                  if (pct < 0.5) return null
                  return (
                    <div
                      key={k}
                      className={`${FILLS[k].className} border-r border-ink/40`}
                      style={{ width: `${pct}%` }}
                      title={`${FILLS[k].label}: contributes ${(pct).toFixed(0)} pts`}
                    />
                  )
                })}
              </div>
            </div>
          </React.Fragment>
        ))}
      </div>

      {/* Formula footnote */}
      <div className="rule-thin pt-3">
        <p className="font-mono text-[11px] text-ink-soft leading-relaxed">
          index = 100 × ( w<sub>tone</sub>·Δtone + w<sub>lex</sub>·lexical + w<sub>om</sub>·omission +
          w<sub>cons</sub>·consistency + dissonance ) ÷ 1.3
        </p>
        <p className="font-serif text-xs text-ink-faint mt-1">
          A small <em>dissonance</em> penalty is added when a source’s tone clashes with the emotional
          weight of the verified facts (e.g. an upbeat spin on tragic facts).
        </p>
      </div>
    </div>
  )
}

export default BiasIndexExplainer
