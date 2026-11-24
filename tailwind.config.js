/**
 * Paleta del producto: fondo claro y azul oscuro para una lectura ejecutiva.
 */
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        marca: "#1E3A5F",
      },
      fontFamily: {
        sans: ["Segoe UI", "Tahoma", "sans-serif"],
      },
    },
  },
  plugins: [],
};
