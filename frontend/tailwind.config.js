/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          bg: '#F7F8F6',
          secondary: '#EFF3F1',
          surface: '#FFFFFF',
          primary: '#087E8B',
          'primary-hover': '#075C66',
          soft: '#DCEFF0',
          border: '#DCE4E3',
          text: '#172B3A',
          muted: '#526773',
        },
        teal: {
          50: '#F0F9FA',
          100: '#DCEFF0',
          200: '#B5E1E4',
          300: '#80CAD0',
          400: '#40ADB8',
          500: '#087E8B',
          600: '#087E8B',
          700: '#075C66',
          800: '#064951',
          900: '#04343B',
        },
        navy: {
          50: '#F0F4F8',
          100: '#D9E2EC',
          200: '#BCCCDC',
          600: '#526773',
          800: '#1E364A',
          900: '#172B3A',
        },
        slate: {
          850: '#151f33',
        },
      }
    },
  },
  plugins: [],
}
