/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Newspaper ink-on-paper palette (monochrome).
        paper: "#f4f1e8",
        "paper-dark": "#e9e4d6",
        ink: "#14110c",
        "ink-soft": "#3a352c",
        "ink-faint": "#6b6559",
        rule: "#14110c",
        stamp: "#8a1c1c", // reserved, used sparingly for "high bias" stamps
      },
      fontFamily: {
        display: ['"Playfair Display"', "Georgia", "serif"],
        serif: ['"PT Serif"', "Georgia", "serif"],
        type: ['"Special Elite"', '"Courier New"', "monospace"],
        mono: ['"IBM Plex Mono"', "monospace"],
      },
      boxShadow: {
        paper: "0 1px 0 #14110c, 0 2px 12px rgba(20,17,12,0.12)",
      },
      keyframes: {
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.15" },
        },
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 rgba(20,17,12,0.5)" },
          "70%": { boxShadow: "0 0 0 10px rgba(20,17,12,0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(20,17,12,0)" },
        },
        "ticker": {
          "0%": { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
      },
      animation: {
        blink: "blink 1s steps(2, start) infinite",
        "pulse-ring": "pulse-ring 1.4s ease-out infinite",
        ticker: "ticker 30s linear infinite",
      },
    },
  },
  plugins: [],
}
