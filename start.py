#!/usr/bin/env python3
"""
Launcher unificado em Python:
Inicia a simulação paralela CUDA na RTX 3060 e o estúdio React automaticamente.
"""
import sys
import subprocess

if __name__ == "__main__":
    cmd = [sys.executable, "train_slither_cuda.py"] + sys.argv[1:]
    subprocess.run(cmd)
