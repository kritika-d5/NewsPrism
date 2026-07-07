import React from 'react'
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom'
import SearchPage from './pages/SearchPage'
import ClusterDetailPage from './pages/ClusterDetailPage'

function Masthead() {
  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })

  return (
    <header className="bg-paper">
      <div className="max-w-6xl mx-auto px-4">
        {/* top dateline strip */}
        <div className="flex justify-between items-center py-1.5 text-[11px] dateline uppercase tracking-wide">
          <span>Vol. I · No. 1</span>
          <span className="hidden sm:block">{today}</span>
          <span>Price: Free · Analysis Edition</span>
        </div>
        <div className="rule-thick" />
        <div className="rule-thin mt-0.5" />

        {/* masthead title */}
        <Link to="/" className="block text-center pt-4 pb-1">
          <h1 className="headline text-6xl sm:text-8xl tracking-tight">NewsPrism</h1>
        </Link>
        <p className="text-center kicker mb-1">The Agentic Bias Ledger</p>
        <p className="text-center font-serif italic text-ink-faint text-sm mb-3">
          “Sine ira et studio” — the same event, read through every source’s lens
        </p>

        <div className="rule-thin" />
        <nav className="flex justify-center gap-6 py-1.5 text-[11px] dateline uppercase tracking-widest">
          <span>Semantic Clustering</span>
          <span className="text-ink-faint">·</span>
          <span>Fact Verification</span>
          <span className="text-ink-faint">·</span>
          <span>Dynamic Bias Index</span>
        </nav>
        <div className="rule-double" />
      </div>
    </header>
  )
}

function App() {
  return (
    <Router>
      <div className="min-h-screen">
        <Masthead />
        <main className="max-w-6xl mx-auto px-4 py-6">
          <Routes>
            <Route path="/" element={<SearchPage />} />
            <Route path="/cluster/:clusterId" element={<ClusterDetailPage />} />
          </Routes>
        </main>
        <footer className="max-w-6xl mx-auto px-4 pb-10 pt-6">
          <div className="rule-thin" />
          <p className="text-center text-[11px] dateline uppercase tracking-widest text-ink-faint pt-3">
            NewsPrism · React · FastAPI · MongoDB · SentenceTransformers · spaCy · Groq
          </p>
        </footer>
      </div>
    </Router>
  )
}

export default App
