/**
 * Arranca FastAPI en el puerto 8000 usando el Python del entorno local.
 * Así «npm run dev» levanta la interfaz y la API con un solo comando.
 */
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const windows = process.platform === "win32";
const enEntorno = windows
  ? path.join(".venv", "Scripts", "python.exe")
  : path.join(".venv", "bin", "python");
const python = fs.existsSync(enEntorno) ? enEntorno : windows ? "python" : "python3";

const proceso = spawn(
  python,
  ["-m", "uvicorn", "api.index:app", "--host", "127.0.0.1", "--port", "8000"],
  { stdio: "inherit" }
);

proceso.on("exit", (codigo) => process.exit(codigo ?? 0));
