import React from 'react'

export function biasLabel(v) {
  if (v >= 70) return 'Heavily Framed'
  if (v >= 40) return 'Noticeably Framed'
  if (v >= 20) return 'Lightly Framed'
  return 'Measured'
}

function ClusterCard({ cluster, index, onClick }) {
  const results = cluster.bias_results || []
  const avgBias = results.length
    ? results.reduce((s, r) => s + (r.bias_index || 0), 0) / results.length
    : 0
  const sources = [...new Set(results.map((r) => r.source).filter(Boolean))]

  return (
    <article
      onClick={onClick}
      className="card p-5 cursor-pointer hover:-translate-y-0.5 hover:shadow-[5px_5px_0_rgba(20,17,12,0.9)] transition-all"
    >
      <div className="flex items-baseline justify-between mb-2">
        <span className="kicker">Story Cluster № {String(index + 1).padStart(2, '0')}</span>
        <span className="dateline text-xs text-ink-faint">
          {cluster.articles_count} art. · {cluster.facts_count} facts
        </span>
      </div>

      <div className="rule-thin mb-3" />

      <h4 className="headline text-2xl leading-tight mb-3">
        {sources.length
          ? `${sources.length} outlet${sources.length === 1 ? '' : 's'} on the same event`
          : 'Coverage cluster'}
      </h4>

      {/* Bias meter */}
      <div className="mb-3">
        <div className="flex justify-between items-baseline mb-1">
          <span className="kicker">Avg. Bias Index</span>
          <span className="font-mono text-sm font-semibold">{avgBias.toFixed(0)}<span className="text-ink-faint">/100</span></span>
        </div>
        <div className="h-3 border border-ink relative overflow-hidden">
          <div className="h-full halftone" style={{ width: `${Math.min(100, avgBias)}%` }} />
        </div>
        <p className="dateline text-[11px] uppercase tracking-wider mt-1 text-ink-soft">{biasLabel(avgBias)}</p>
      </div>

      {sources.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {sources.slice(0, 5).map((s, i) => (
            <span key={i} className="px-1.5 py-0.5 text-[10px] font-mono border border-ink-faint text-ink-soft">
              {s}
            </span>
          ))}
          {sources.length > 5 && (
            <span className="px-1.5 py-0.5 text-[10px] font-mono text-ink-faint">+{sources.length - 5}</span>
          )}
        </div>
      )}

      <div className="rule-thin pt-2 flex justify-between items-center">
        <span className="dateline text-xs text-ink-faint">Full framing analysis</span>
        <span className="font-display font-bold text-sm">Read the ledger →</span>
      </div>
    </article>
  )
}

export default ClusterCard
