import React, { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { analyzeQueryStream } from '../services/api'
import SearchForm from '../components/SearchForm'
import AgentPipeline from '../components/AgentPipeline'
import ClusterCard from '../components/ClusterCard'

function SearchPage() {
  const [running, setRunning] = useState(false)
  const [finished, setFinished] = useState(false)
  const [events, setEvents] = useState([])
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  const handleSearch = useCallback(async (formData) => {
    setRunning(true)
    setFinished(false)
    setEvents([])
    setResults(null)
    setError(null)

    try {
      const result = await analyzeQueryStream(
        {
          query: formData.query,
          dateFrom: formData.dateFrom,
          dateTo: formData.dateTo,
          sources: formData.sources,
        },
        (event) => {
          if (event.type === 'agent') {
            setEvents((prev) => [...prev, event])
          }
        },
      )
      setResults(result)
    } catch (err) {
      setError(err.message || 'The presses jammed. Please try again.')
    } finally {
      setRunning(false)
      setFinished(true)
    }
  }, [])

  const clusters = results?.clusters || []

  return (
    <div className="space-y-6">
      {/* Lede + search */}
      <section className="grid lg:grid-cols-5 gap-6 items-start">
        <div className="lg:col-span-3">
          <p className="kicker mb-2">Investigative Desk</p>
          <h2 className="headline text-4xl sm:text-5xl mb-3 leading-none">
            Read one event through every outlet’s lens.
          </h2>
          <p className="font-serif text-ink-soft text-[15px] leading-relaxed drop-cap">
            Enter any story. A newsroom of autonomous agents fans out across the wire,
            scrapes the full text, groups coverage of the same event, verifies the facts
            each source reports — and computes a transparent <span className="smallcaps font-bold">Bias
            Index</span> that weighs tone, loaded language, omission and consistency. Watch
            them work below.
          </p>
        </div>
        <div className="lg:col-span-2 card p-5">
          <p className="kicker mb-3 pb-2 border-b border-ink">File a Story</p>
          <SearchForm onSubmit={handleSearch} disabled={running} />
        </div>
      </section>

      {error && (
        <div className="card-flat border-stamp p-4">
          <p className="kicker text-stamp mb-1">Stop Press</p>
          <p className="font-serif text-ink">{error}</p>
        </div>
      )}

      {(running || events.length > 0) && (
        <AgentPipeline events={events} finished={finished} />
      )}

      {results && (
        <section className="space-y-4">
          <div className="rule-double" />
          <div className="flex items-baseline justify-between flex-wrap gap-2">
            <h3 className="headline text-3xl">The Coverage</h3>
            <p className="dateline text-sm text-ink-soft">
              {results.total_articles} articles · {clusters.length} event cluster
              {clusters.length === 1 ? '' : 's'}
            </p>
          </div>

          {clusters.length > 0 ? (
            <div className="grid md:grid-cols-2 gap-5">
              {clusters.map((cluster, idx) => (
                <ClusterCard
                  key={cluster.cluster_id}
                  cluster={cluster}
                  index={idx}
                  onClick={() => navigate(`/cluster/${cluster.cluster_id}`)}
                />
              ))}
            </div>
          ) : (
            <div className="card-flat p-6 text-center font-serif text-ink-soft">
              No clusters made the front page. Try a broader or more current query.
            </div>
          )}
        </section>
      )}
    </div>
  )
}

export default SearchPage
