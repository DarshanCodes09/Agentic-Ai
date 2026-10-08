/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["Georgia", "ui-serif", "serif"]
      },
      colors: {
        ink: "#171717",
        muted: "#6f6a62",
        paper: "#faf9f6",
        line: "#e8e3dc",
        surface: "#ffffff"
      },
      boxShadow: {
        soft: "0 16px 45px rgba(23, 23, 23, 0.06)"
      }
    }
  },
  plugins: []
};
