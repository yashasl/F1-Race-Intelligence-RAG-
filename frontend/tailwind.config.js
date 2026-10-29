/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["'Inter'", "sans-serif"],
        body: ["'Inter'", "sans-serif"],
      },
      colors: {
        dark: "#0a0a0f",
        charcoal: "#12121a",
        muted: "#444455",
        accent: "#ff2a40",
      },
    },
  },
  plugins: [],
};
