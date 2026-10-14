"""Script Utilitário para Instalação Opcional do Motor Stockfish Windows.

Permite baixar e configurar automaticamente o executável do Stockfish na pasta bin/
para quem deseja cálculo instantâneo em mais de 3500 Elo.
"""

import os
import sys
import zipfile
import urllib.request
from pathlib import Path

STOCKFISH_URL = "https://github.com/official-stockfish/Stockfish/releases/download/sf_16/stockfish-windows-x86-64-modern.zip"


def download_and_setup_stockfish():
    current_dir = Path(__file__).resolve().parent
    bin_dir = current_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    target_exe = bin_dir / "stockfish.exe"

    if target_exe.is_file():
        print(f"[OK] Stockfish já está instalado em: {target_exe}")
        return True

    zip_path = bin_dir / "stockfish.zip"
    print(f"[*] Baixando Stockfish oficial de: {STOCKFISH_URL}")
    print("[*] Aguarde o download (~34 MB)...")

    try:
        urllib.request.urlretrieve(STOCKFISH_URL, zip_path)
        print("[*] Extraindo arquivo ZIP...")
        with zipfile.ZipFile(zip_path, "r") as z:
            # Procurar arquivo executável dentro do zip
            exe_names = [n for n in z.namelist() if n.endswith(".exe")]
            if not exe_names:
                raise RuntimeError("Nenhum .exe encontrado no arquivo baixado.")
            exe_member = exe_names[0]
            with z.open(exe_member) as src, open(target_exe, "wb") as dst:
                dst.write(src.read())

        if zip_path.is_file():
            zip_path.unlink()

        print(f"[SUCESSO] Stockfish instalado com sucesso em: {target_exe}")
        return True
    except Exception as e:
        print(f"[!] Falha ao baixar ou extrair Stockfish: {e}")
        if zip_path.is_file():
            zip_path.unlink()
        return False


if __name__ == "__main__":
    download_and_setup_stockfish()
