/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'bg-base': '#0a0e1a',
        'bg-card': '#1a1f2e',
        'bg-card-hover': '#222838',
        'neon-blue': '#00d4ff',
        'neon-green': '#00ff88',
        'neon-purple': '#a855f7',
        'neon-orange': '#ff8c42',
        'neon-red': '#ff4757',
        'neon-yellow': '#ffd93d',
      },
      fontFamily: {
        sans: ['"PingFang SC"', '"Microsoft YaHei"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Cascadia Code"', 'Consolas', 'monospace'],
      },
      animation: {
        'pulse-glow': 'pulseGlow 1.5s ease-in-out infinite',
        'pulse-green': 'pulseGreen 1.5s ease-in-out infinite',
        'pulse-red': 'pulseRed 1.2s ease-in-out infinite',
        'blink': 'blink 1s step-end infinite',
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'spin-slow': 'spin 2s linear infinite',
        'float': 'float 3s ease-in-out infinite',
        'ripple': 'ripple 2s ease-out infinite',
      },
      keyframes: {
        pulseGlow: {
          '0%, 100%': { boxShadow: '0 0 10px rgba(0, 212, 255, 0.5), 0 0 20px rgba(0, 212, 255, 0.3)' },
          '50%': { boxShadow: '0 0 20px rgba(0, 212, 255, 0.8), 0 0 40px rgba(0, 212, 255, 0.5)' },
        },
        pulseGreen: {
          '0%, 100%': { boxShadow: '0 0 10px rgba(0, 255, 136, 0.5), 0 0 20px rgba(0, 255, 136, 0.3)' },
          '50%': { boxShadow: '0 0 25px rgba(0, 255, 136, 0.9), 0 0 50px rgba(0, 255, 136, 0.6)' },
        },
        pulseRed: {
          '0%, 100%': { boxShadow: '0 0 8px rgba(255, 71, 87, 0.6), 0 0 16px rgba(255, 71, 87, 0.4)' },
          '50%': { boxShadow: '0 0 18px rgba(255, 71, 87, 0.9), 0 0 36px rgba(255, 71, 87, 0.6)' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-6px)' },
        },
        ripple: {
          '0%': { transform: 'scale(0.8)', opacity: '0.7' },
          '100%': { transform: 'scale(2.4)', opacity: '0' },
        },
      },
    },
  },
  plugins: [],
}
