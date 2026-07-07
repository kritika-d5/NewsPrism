import React, { useState } from 'react'

function FrameAnalysis({ frameSummary }) {
  const [selectedPhrase, setSelectedPhrase] = useState(null)

  if (!frameSummary || frameSummary.length === 0) {
    return <p className="font-serif text-sm text-ink-faint">No framing analysis available.</p>
  }

  return (
    <div className="space-y-4">
      {frameSummary.map((frame, idx) => {
        const tone = frame.tone || 0
        return (
          <div key={idx} className="card-flat p-4">
            <div className="flex justify-between items-baseline mb-2">
              <h4 className="font-display font-bold text-lg">{frame.source}</h4>
              <div className="flex items-center gap-3 font-mono text-xs">
                <span title="Bias Index">B {frame.bias_index?.toFixed(0) ?? '—'}</span>
                <span className="text-ink-faint">|</span>
                <span title="Transparency">T {frame.transparency_score?.toFixed(0) ?? '—'}</span>
              </div>
            </div>

            {/* Tone dial: centre = neutral, left = negative, right = positive */}
            <div className="mb-3">
              <div className="flex justify-between kicker mb-1">
                <span>Negative</span>
                <span>Tone</span>
                <span>Positive</span>
              </div>
              <div className="relative h-3 border border-ink">
                <div className="absolute top-0 bottom-0 left-1/2 w-px bg-ink" />
                <div
                  className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 bg-ink border border-ink rotate-45"
                  style={{ left: `calc(${((tone + 1) / 2) * 100}% - 5px)` }}
                  title={`Tone ${tone.toFixed(2)}`}
                />
              </div>
            </div>

            {frame.top_phrases && frame.top_phrases.length > 0 && (
              <div>
                <p className="kicker mb-1.5">Loaded phrases · tap to rewrite</p>
                <div className="flex flex-wrap gap-1.5">
                  {frame.top_phrases.slice(0, 5).map((phrase, pIdx) => (
                    <button
                      key={pIdx}
                      onClick={() => setSelectedPhrase({ phrase, source: frame.source })}
                      className="px-2 py-0.5 text-[11px] font-serif italic border border-ink border-dashed hover:bg-ink hover:text-paper transition-colors"
                      title="See objective alternative"
                    >
                      “{(phrase.phrase || '').substring(0, 32)}…”
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )
      })}

      {selectedPhrase && (
        <PhraseModal
          phrase={selectedPhrase.phrase}
          source={selectedPhrase.source}
          onClose={() => setSelectedPhrase(null)}
        />
      )}
    </div>
  )
}

function PhraseModal({ phrase, source, onClose }) {
  return (
    <div className="fixed inset-0 bg-ink/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="card max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-start border-b border-ink pb-2 mb-3">
          <h3 className="headline text-xl">Phrase Rewrite</h3>
          <button onClick={onClose} className="font-mono text-lg leading-none hover:opacity-60">×</button>
        </div>
        <div className="space-y-3 font-serif text-sm">
          <p className="dateline text-xs text-ink-faint">
            {source} · flagged as {phrase.type || 'loaded'} language
          </p>
          <div>
            <p className="kicker mb-1">As printed</p>
            <p className="bg-[#fdfcf7] border-l-2 border-ink pl-3 py-1 italic">“{phrase.phrase}”</p>
          </div>
          {phrase.reason && (
            <div>
              <p className="kicker mb-1">Why it’s flagged</p>
              <p className="text-ink-soft">{phrase.reason}</p>
            </div>
          )}
          {phrase.objective_alternative && phrase.objective_alternative !== phrase.phrase && (
            <div>
              <p className="kicker mb-1">Neutral rewrite</p>
              <p className="bg-ink text-paper pl-3 pr-2 py-2">“{phrase.objective_alternative}”</p>
            </div>
          )}
        </div>
        <button onClick={onClose} className="btn-ink w-full py-2 mt-4 text-xs">Close</button>
      </div>
    </div>
  )
}

export default FrameAnalysis
