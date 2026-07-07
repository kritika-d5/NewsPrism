import React, { useState } from 'react'

const SUGGESTIONS = ['Israel Gaza ceasefire', 'US election', 'OpenAI', 'India economy', 'climate summit']

function SearchForm({ onSubmit, disabled }) {
  const [query, setQuery] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [sources, setSources] = useState('')

  const submit = (q) => {
    onSubmit({
      query: q,
      dateFrom: dateFrom || null,
      dateTo: dateTo || null,
      sources: sources ? sources.split(',').map((s) => s.trim()).filter(Boolean) : null,
    })
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (query.trim()) submit(query.trim())
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="query" className="kicker block mb-1">Headline / Topic</label>
        <input
          type="text"
          id="query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          required
          disabled={disabled}
          placeholder="e.g. election results, ceasefire talks"
          className="input-ink w-full px-3 py-2 text-[15px]"
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="dateFrom" className="kicker block mb-1">From</label>
          <input
            type="date"
            id="dateFrom"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            disabled={disabled}
            className="input-ink w-full px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label htmlFor="dateTo" className="kicker block mb-1">To</label>
          <input
            type="date"
            id="dateTo"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            disabled={disabled}
            className="input-ink w-full px-3 py-2 text-sm"
          />
        </div>
      </div>

      <div>
        <label htmlFor="sources" className="kicker block mb-1">Restrict Outlets (optional)</label>
        <input
          type="text"
          id="sources"
          value={sources}
          onChange={(e) => setSources(e.target.value)}
          disabled={disabled}
          placeholder="bbc-news, cnn, reuters"
          className="input-ink w-full px-3 py-2 text-sm"
        />
      </div>

      <button
        type="submit"
        disabled={disabled || !query.trim()}
        className="btn-ink w-full py-2.5 text-sm"
      >
        {disabled ? 'Presses Running…' : 'Run the Newsroom ▸'}
      </button>

      {!disabled && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => { setQuery(s); submit(s) }}
              className="px-2 py-0.5 text-[10px] font-mono border border-ink-faint text-ink-soft hover:bg-ink hover:text-paper transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </form>
  )
}

export default SearchForm
