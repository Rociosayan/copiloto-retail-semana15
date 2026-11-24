/**
 * Conecta la interfaz con la API.
 * En local las rutas /api/py van al proceso de Python; en Vercel se quedan en el mismo dominio.
 */

/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/py/:path*",
        destination:
          process.env.NODE_ENV === "development"
            ? "http://127.0.0.1:8000/api/py/:path*"
            : "/api/",
      },
    ];
  },
};

module.exports = nextConfig;
