import React from 'react'
import { Bar } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend)

const INK = '#14110c'

function BiasChart({ articles, frameSummary }) {
  const sources =
    frameSummary ||
    articles?.map((a) => ({
      source: a.source,
      bias_index: a.bias_index || 0,
      transparency_score: 100 - (a.omission_score || 0) * 100,
    })) ||
    []

  if (sources.length === 0) {
    return <p className="font-serif text-sm text-ink-faint">No data available for chart.</p>
  }

  const data = {
    labels: sources.map((s) => s.source),
    datasets: [
      {
        label: 'Bias Index',
        data: sources.map((s) => s.bias_index || 0),
        backgroundColor: INK,
        borderColor: INK,
        borderWidth: 1,
      },
      {
        label: 'Transparency',
        data: sources.map((s) => s.transparency_score || 0),
        backgroundColor: 'rgba(20,17,12,0.28)',
        borderColor: INK,
        borderWidth: 1,
      },
    ],
  }

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    font: { family: "'IBM Plex Mono', monospace" },
    plugins: {
      legend: {
        position: 'top',
        labels: { font: { family: "'IBM Plex Mono', monospace", size: 11 }, color: INK, boxWidth: 12 },
      },
      title: { display: false },
      tooltip: {
        backgroundColor: INK,
        titleFont: { family: "'IBM Plex Mono', monospace" },
        bodyFont: { family: "'IBM Plex Mono', monospace" },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        max: 100,
        grid: { color: 'rgba(20,17,12,0.12)' },
        ticks: { color: INK, font: { family: "'IBM Plex Mono', monospace", size: 10 } },
      },
      x: {
        grid: { display: false },
        ticks: { color: INK, font: { family: "'IBM Plex Mono', monospace", size: 10 } },
      },
    },
  }

  return (
    <div style={{ height: '320px' }}>
      <Bar data={data} options={options} />
    </div>
  )
}

export default BiasChart
