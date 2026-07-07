import React from 'react'

function LoadingSpinner({ label = 'Setting type…' }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-8">
      <div className="w-10 h-10 border-2 border-ink border-t-transparent rounded-full animate-spin" />
      <p className="kicker">{label}</p>
    </div>
  )
}

export default LoadingSpinner
