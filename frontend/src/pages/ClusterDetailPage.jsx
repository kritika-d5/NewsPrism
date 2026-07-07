import React, { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getCluster } from '../services/api'
import LoadingSpinner from '../components/LoadingSpinner'
import FactSummary from '../components/FactSummary'
import FrameAnalysis from '../components/FrameAnalysis'
import BiasChart from '../components/BiasChart'
import BiasIndexExplainer from '../components/BiasIndexExplainer'
import FactHeatmap from '../components/FactHeatmap'
import { biasLabel } from '../components/ClusterCard'

function Panel({ kicker, title, children, className = '' }) {
  return (
    <section className={`card p-5 ${className}`}>
      {kicker && <p className="kicker mb-1">{kicker}</p>}
      {title && <h3 className="headline text-2xl mb-3 border-b border-ink pb-2">{title}</h3>}
      {children}
    </section>
  )
}

function ClusterDetailPage() {
  const { clusterId } = useParams()
  const [cluster, setCluster] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    getCluster(clusterId)
      .then((data) => active && setCluster(data))
      .catch((err) => active && setError(err.response?.data?.detail || err.message || 'Failed to load cluster'))
      .finally(() => active && setLoading(false))
    return () => { active = false }
  }, [clusterId])

  if (loading) return <LoadingSpinner label="Pulling the archive…" />
  if (error) {
    return (
      <div className="card-flat border-stamp p-4">
        <p className="kicker text-stamp mb-1">Stop Press</p>
        <p className="font-serif">{error}</p>
      </div>
    )
  }
  if (!cluster) return <p className="font-serif text-ink-faint">Cluster not found.</p>

  const canonical =
    cluster.articles?.find((a) => a.id === cluster.canonical_article_id) || cluster.articles?.[0]
  const opposing = findOpposingArticle(cluster.articles, canonical)
  const avgBias = averageBias(cluster.articles)

  return (
    <div className="space-y-6">
      <Link to="/" className="dateline text-xs uppercase tracking-widest hover:opacity-60">
        ‹ Back to the front page
      </Link>

      {/* Cluster header */}
      <header>
        <p className="kicker mb-2">
          {cluster.news_category || 'Coverage'} · Cluster Analysis
        </p>
        <h2 className="headline text-4xl sm:text-5xl leading-none mb-3">“{cluster.query}”</h2>
        <div className="rule-thin mb-2" />
        <div className="flex flex-wrap gap-x-5 gap-y-1 dateline text-sm text-ink-soft">
          <span>{cluster.articles?.length || 0} articles</span>
          <span>Avg. Bias {avgBias.toFixed(0)}/100 · {biasLabel(avgBias)}</span>
          {cluster.created_at && <span>Filed {new Date(cluster.created_at).toLocaleDateString()}</span>}
        </div>
      </header>

      {/* Dissenting column */}
      {opposing && (
        <section className="card-flat p-4 border-l-4 border-ink">
          <p className="kicker mb-1">The Dissenting Column</p>
          <p className="font-serif text-sm text-ink-soft mb-2">
            <span className="font-bold">{opposing.source}</span> frames this event most differently from
            the rest of the pack.
          </p>
          <p className="font-serif italic text-ink">{opposing.title}</p>
          {opposing.url && (
            <a href={opposing.url} target="_blank" rel="noopener noreferrer"
               className="dateline text-xs uppercase tracking-widest mt-2 inline-block hover:opacity-60">
              Read the dissent →
            </a>
          )}
        </section>
      )}

      <div className="grid lg:grid-cols-2 gap-6">
        <Panel kicker="Cross-checked" title="The Facts">
          <FactSummary facts={cluster.facts} summary={cluster.fact_summary} />
        </Panel>
        <Panel kicker="Source by source" title="Framing Analysis">
          <FrameAnalysis frameSummary={cluster.frame_summary} />
        </Panel>
      </div>

      <Panel kicker="Methodology · Transparent Scoring" title="Anatomy of the Bias Index">
        <BiasIndexExplainer articles={cluster.articles} weights={cluster.bias_weights} />
      </Panel>

      <Panel kicker="At a glance" title="Bias vs. Transparency">
        <BiasChart articles={cluster.articles} frameSummary={cluster.frame_summary} />
      </Panel>

      <Panel kicker="Who reported what" title="Omission Grid">
        <FactHeatmap facts={cluster.facts} articles={cluster.articles} />
      </Panel>

      <Panel kicker="The full cut" title="Articles in this Cluster">
        <div className="space-y-4">
          {cluster.articles?.map((article) => (
            <ArticleCard key={article.id} article={article} />
          ))}
        </div>
      </Panel>
    </div>
  )
}

function averageBias(articles) {
  const scored = (articles || []).filter((a) => a.bias_index != null)
  if (!scored.length) return 0
  return scored.reduce((s, a) => s + a.bias_index, 0) / scored.length
}

function findOpposingArticle(articles, canonical) {
  if (!articles || !canonical || articles.length < 2) return null
  return articles.reduce((best, curr) => {
    if (curr.id === canonical.id) return best
    const diff =
      Math.abs((curr.tone_score || 0) - (canonical.tone_score || 0)) +
      Math.abs((curr.lexical_bias_score || 0) - (canonical.lexical_bias_score || 0))
    const bestDiff = best
      ? Math.abs((best.tone_score || 0) - (canonical.tone_score || 0)) +
        Math.abs((best.lexical_bias_score || 0) - (canonical.lexical_bias_score || 0))
      : -1
    return diff > bestDiff ? curr : best
  }, null)
}

function ArticleCard({ article }) {
  const [showOmissions, setShowOmissions] = useState(false)
  const missing = article.missing_facts || []
  const bias = article.bias_index

  return (
    <div className="border-b hairline border-b pb-4">
      <div className="flex justify-between items-baseline gap-3 mb-1">
        <h4 className="font-display font-bold text-lg leading-tight">{article.title}</h4>
        {bias != null && (
          <span className="font-mono text-xs whitespace-nowrap border border-ink px-1.5 py-0.5">
            Bias {bias.toFixed(0)}
          </span>
        )}
      </div>
      <p className="dateline text-xs text-ink-faint mb-2 uppercase tracking-wide">
        {article.source}
        {article.published_at ? ` · ${new Date(article.published_at).toLocaleDateString()}` : ''}
      </p>
      <p className="font-serif text-sm text-ink-soft leading-relaxed">
        {(article.text || '').substring(0, 220)}…
      </p>

      {missing.length > 0 && (
        <div className="mt-2">
          <button
            onClick={() => setShowOmissions((v) => !v)}
            className="dateline text-xs uppercase tracking-wider hover:opacity-60"
          >
            ▸ {missing.length} key omission{missing.length === 1 ? '' : 's'} {showOmissions ? '(hide)' : '(show)'}
          </button>
          {showOmissions && (
            <ul className="mt-2 border-l-2 border-ink pl-3 space-y-1">
              {missing.slice(0, 4).map((f, i) => (
                <li key={i} className="font-serif text-xs text-ink-soft">— {f.fact?.substring(0, 140)}…</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {article.url && (
        <a href={article.url} target="_blank" rel="noopener noreferrer"
           className="dateline text-xs uppercase tracking-widest mt-2 inline-block hover:opacity-60">
          Read full article →
        </a>
      )}
    </div>
  )
}

export default ClusterDetailPage
