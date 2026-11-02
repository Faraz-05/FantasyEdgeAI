/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#090d18",
        panel: "#111827",
        lime: "#c7f36b",
        cyan: "#59d9d0"
      },
      boxShadow: {
        glow: "0 0 32px rgba(199, 243, 107, 0.12)"
      }
    }
  },
  plugins: []
};
