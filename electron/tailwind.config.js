/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './index.html',
    './src/renderer/**/*.{vue,ts,js}',
  ],
  theme: {
    extend: {
      colors: {
        'app': '#121B26',
        'surface': 'rgba(20, 32, 48, 0.6)',
        'text-primary': '#E0E0E0',
        'text-muted': '#828282',
        'accent-green': '#27AE60',
        'accent-red': '#EB5757',
        'accent-blue': '#3B82F6',
      },
      backdropBlur: {
        'glass': '16px',
      },
      borderRadius: {
        '2xl': '16px',
        'xl': '12px',
        'lg': '8px',
      },
      fontFamily: {
        'plus-jakarta': ['"Plus Jakarta Sans"', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
