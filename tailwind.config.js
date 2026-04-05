** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        green: {
          500: 'rgb(var(--color-green) / <alpha-value>)',
        },
        amber: {
          500: 'rgb(var(--color-amber) / <alpha-value>)',
        },
        red: {
          500: 'rgb(var(--color-red) / <alpha-value>)',
        },
        blue: {
          500: 'rgb(var(--color-blue) / <alpha-value>)',
        },
        purple: {
          500: 'rgb(var(--color-purple) / <alpha-value>)',
        },
      },
      animation: {
        pulse: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'spin-slow': 'spin 20s linear infinite',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};