/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./pages/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
    "./hooks/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Brand tokens: the same values as the CSS variables in app/globals.css.
        brand: {
          blue: "#2563EB",
          teal: "#00BFA6",
          navy: "#06182F",
          "navy-soft": "#082A46",
        },
        ink: {
          DEFAULT: "#0B1220",
          muted: "#64748B",
        },
        surface: {
          DEFAULT: "#FFFFFF",
          soft: "#F8FBFF",
          page: "#F4FAFF",
        },
        line: {
          DEFAULT: "#DCE8F5",
          strong: "#C9DAEE",
        },
        calm: {
          background: "#F8FAFC",
          text: "#111827",
          muted: "#6B7280",
          lavender: "#A78BFA",
          success: "#22C55E",
          warning: "#F59E0B",
          error: "#EF4444",
        },
      },
      fontFamily: {
        sans: [
          "var(--font-poppins)",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
      },
      borderRadius: {
        card: "16px",
        control: "12px",
      },
      boxShadow: {
        calm: "0 24px 70px rgba(15, 23, 42, 0.10)",
        card: "0 1px 2px rgba(15, 23, 42, 0.04), 0 8px 24px rgba(15, 23, 42, 0.04)",
        "card-hover": "0 1px 2px rgba(15, 23, 42, 0.05), 0 12px 32px rgba(15, 23, 42, 0.08)",
        focus: "0 0 0 4px rgba(37, 99, 235, 0.15)",
      },
    },
  },
  plugins: [],
}
