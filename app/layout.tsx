/**
 * Marco de la aplicación. El dashboard ocupa toda la ventana
 * y el asistente se abre desde un botón flotante.
 */
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Copiloto Comercial Retail",
  description: "Dashboard de ventas y asistente para la gerencia comercial.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
