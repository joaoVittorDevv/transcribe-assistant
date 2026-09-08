/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './index.html',
    './src/renderer/**/*.{vue,ts,js}',
  ],
  theme: {
    extend: {
      colors: {
        'app': '#13151A',
        'canvas': '#13151A',
        'surface-muted': '#1A1D24',
        'surface-raised': '#222733',
        'surface-elevated': '#2A303F',
        'border-subtle': '#2D3342',
        'border-active': '#3F444E',
        'surface': 'rgba(26, 29, 36, 0.85)',
        'text-primary': '#DDE2F6',
        'text-secondary': '#909095',
        'text-muted': '#828282',
        'accent-green': '#10B981',
        'accent-red': '#EF4444',
        'accent-blue': '#3B82F6',
        'accent-amber': '#F59E0B',
        'accent-cobalt': '#3B82F6',
      },
      backdropBlur: {
        'glass': '16px',
      },
      borderRadius: {
        '2xl': '16px',
        'xl': '12px',
        'lg': '8px',
        'md': '6px',
        'sm': '4px',
      },
      fontFamily: {
        'inter': ['Inter', 'sans-serif'],
        'plus-jakarta': ['"Plus Jakarta Sans"', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
