/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        counseling: {
          'bg-tint': '#EFF6FF',
          'subtle-fill': '#DBEAFE',
          'light-accent': '#BFDBFE',
          'muted-text': '#93C5FD',
          'primary': '#60A5FA',
          'hover-primary': '#3B82F6',
          'active-focus': '#2563EB',
          'high-contrast': '#1D4ED8',
          'deep-contrast': '#1E3A8A',
        },
      },
    },
  },
  plugins: [],
}
