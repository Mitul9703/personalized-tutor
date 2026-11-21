/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1a1a1a",
        paper: "#faf8f6",
        panel: "#ffffff",
        line: "#e7e2e3",
        // primary: deep maroon
        brand: "#8c1d40",
        branddark: "#6d152f",
        brandsoft: "#f6e8ec",
        // accent: gold
        gold: "#ffc627",
        goldsoft: "#fff4d6",
        goldink: "#7a5a00",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
