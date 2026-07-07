import React from 'react'

const STATUS_MARK = {
  supported: '✓',
  contradicted: '✕',
  unverified: '?',
}

function FactSummary({ facts, summary }) {
  const verified = (facts || []).filter(
    (f) => f.status === 'supported' || f.status === 'contradicted',
  )

  return (
    <div className="space-y-4">
      {summary && (
        <div className="border-l-2 border-ink pl-3">
          <p className="kicker mb-1">The Wire, in brief</p>
          <p className="font-serif text-[15px] text-ink leading-relaxed whitespace-pre-line">{summary}</p>
        </div>
      )}

      {verified.length > 0 ? (
        <div className="space-y-2">
          <p className="kicker">
            Verified facts · {verified.length} of {facts.length} claims
          </p>
          {verified.map((fact, idx) => (
            <div key={idx} className="flex gap-3 border-b hairline border-b pb-2">
              <span
                className={`font-mono text-base leading-none mt-1 ${
                  fact.status === 'contradicted' ? 'text-stamp' : 'text-ink'
                }`}
                title={fact.status}
              >
                {STATUS_MARK[fact.status] || '?'}
              </span>
              <div className="flex-1">
                <p className="font-serif text-sm text-ink leading-snug">{fact.fact}</p>
                <p className="dateline text-[11px] text-ink-faint mt-0.5 uppercase tracking-wide">
                  {fact.status} · {fact.sources?.length || 0} source
                  {(fact.sources?.length || 0) === 1 ? '' : 's'}
                </p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="font-serif text-sm text-ink-faint">No cross-verified facts for this cluster.</p>
      )}
    </div>
  )
}

export default FactSummary
