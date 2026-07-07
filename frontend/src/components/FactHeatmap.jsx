import React from 'react'

// Monochrome fact × source presence grid. A filled (halftone) cell means the
// source reported the fact; an empty cell means it was omitted.
function FactHeatmap({ facts, articles }) {
  if (!facts?.length || !articles?.length) {
    return <p className="font-serif text-sm text-ink-faint">No data available for the omission grid.</p>
  }

  const sources = [...new Set(articles.map((a) => a.source))]
  const present = (fact, source) => {
    const article = articles.find((a) => a.source === source)
    if (!article) return false
    const keywords = (fact.fact || '').toLowerCase().split(' ').filter((w) => w.length > 3)
    const text = (article.text || '').toLowerCase()
    return keywords.some((k) => text.includes(k))
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full border-collapse text-xs">
        <thead>
          <tr>
            <th className="border border-ink p-2 text-left kicker bg-ink text-paper">Fact \ Source</th>
            {sources.map((s, i) => (
              <th key={i} className="border border-ink p-2 font-mono text-[10px] align-bottom" title={s}>
                {s?.substring(0, 14)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {facts.slice(0, 12).map((fact, fi) => (
            <tr key={fi}>
              <td className="border border-ink p-2 font-serif max-w-xs">
                <span title={fact.fact}>{fact.fact?.substring(0, 60)}…</span>
              </td>
              {sources.map((s, si) => {
                const yes = present(fact, s)
                return (
                  <td
                    key={si}
                    className={`border border-ink w-10 h-8 text-center ${yes ? 'halftone' : ''}`}
                    title={yes ? 'Reported' : 'Omitted'}
                  />
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-3 flex items-center gap-5 text-xs font-mono">
        <span className="flex items-center gap-2"><span className="w-4 h-4 border border-ink halftone" /> Reported</span>
        <span className="flex items-center gap-2"><span className="w-4 h-4 border border-ink" /> Omitted</span>
      </div>
    </div>
  )
}

export default FactHeatmap
