/**
 * =============================================================================
 * SLITHER AI - UNIFIED LAUNCHER (1 COMANDO PARA TUDO)
 * Inicia simultaneamente:
 *  1. Motor Tensorial PyTorch CUDA (NVIDIA RTX 3060 - 5 Instâncias x 500 Bots = 2.500 na VRAM)
 *  2. Estúdio Web React Vite (Interface Unificada Oficial em http://localhost:3000/)
 * =============================================================================
 */

import { spawn, execSync } from 'child_process';
import path from 'path';
import http from 'http';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Cores ANSI para o terminal
const CYAN = '\x1b[36m';
const GREEN = '\x1b[32m';
const YELLOW = '\x1b[33m';
const MAGENTA = '\x1b[35m';
const BOLD = '\x1b[1m';
const RESET = '\x1b[0m';

console.log(`${BOLD}${CYAN}========================================================================${RESET}`);
console.log(`${BOLD}${GREEN}  SLITHER AI - ESTÚDIO UNIFICADO (NVIDIA RTX 3060 + REACT VITE)${RESET}`);
console.log(`${BOLD}${CYAN}  5 Instâncias Paralelas (Island Model) x 500 Bots = 2.500 na VRAM     ${RESET}`);
console.log(`${BOLD}${CYAN}========================================================================${RESET}`);
console.log(`${YELLOW}[*] Modo 100% Integrado: Tudo em 1 único comando!${RESET}`);
console.log(`${CYAN}[1/2] Iniciando Motor Tensorial CUDA (5 Instâncias x 500 Bots)...${RESET}`);
console.log(`${GREEN}[2/2] Iniciando Estúdio React Oficial (http://localhost:3000/)...${RESET}`);
console.log(`${BOLD}${CYAN}------------------------------------------------------------------------${RESET}\n`);

const isWin = process.platform === 'win32';
let pythonProc = null;
let viteProc = null;
let isCleaningUp = false;

function killProcessTree(proc) {
  if (!proc || !proc.pid) return;
  try {
    if (isWin) {
      execSync(`taskkill /pid ${proc.pid} /T /F`, { stdio: 'ignore' });
    } else {
      proc.kill('SIGKILL');
    }
  } catch (e) {
    // Processo já encerrado
  }
}

function cleanup() {
  if (isCleaningUp) return;
  isCleaningUp = true;
  console.log(`\n${YELLOW}[*] Encerrando processos com segurança...${RESET}`);
  killProcessTree(pythonProc);
  killProcessTree(viteProc);
  console.log(`${GREEN}[✓] Estúdio e Motor CUDA finalizados. Até a próxima!${RESET}\n`);
  process.exit(0);
}

process.on('SIGINT', cleanup);
process.on('SIGTERM', cleanup);

const pythonCmd = isWin ? 'python' : 'python3';
const pythonFullCmd = `${pythonCmd} train_slither_cuda.py --instances 5 --bots-per-instance 500 --generations 10000`;
pythonProc = spawn(pythonFullCmd, {
  cwd: __dirname,
  env: { ...process.env, PYTHONUNBUFFERED: '1' },
  shell: true,
});

pythonProc.stdout.on('data', (data) => {
  const lines = data.toString().split('\n');
  for (const line of lines) {
    if (line.trim()) {
      console.log(`${CYAN}[CUDA-GPU]${RESET} ${line}`);
    }
  }
});

pythonProc.stderr.on('data', (data) => {
  const lines = data.toString().split('\n');
  for (const line of lines) {
    if (line.trim()) {
      console.error(`${MAGENTA}[CUDA-LOG]${RESET} ${line}`);
    }
  }
});

pythonProc.on('close', (code) => {
  if (!isCleaningUp) {
    console.log(`${YELLOW}[!] Processo Python encerrou com código ${code}${RESET}`);
  }
});

// 2. Iniciar Vite Dev Server
const viteFullCmd = 'npx vite --port=3000 --host=0.0.0.0';
viteProc = spawn(viteFullCmd, {
  cwd: __dirname,
  shell: true,
});

viteProc.stdout.on('data', (data) => {
  const lines = data.toString().split('\n');
  for (const line of lines) {
    if (line.trim()) {
      console.log(`${GREEN}[REACT-UI]${RESET} ${line}`);
    }
  }
});

viteProc.stderr.on('data', (data) => {
  const lines = data.toString().split('\n');
  for (const line of lines) {
    if (line.trim()) {
      console.error(`${YELLOW}[REACT-WARN]${RESET} ${line}`);
    }
  }
});

viteProc.on('close', (code) => {
  if (!isCleaningUp) {
    console.log(`${YELLOW}[!] Processo Vite encerrou com código ${code}${RESET}`);
    cleanup();
  }
});
