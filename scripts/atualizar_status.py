#!/usr/bin/env python3
"""
Atualiza status/hoje.json com o resultado de uma automação do dia.

Usado pelos workflows do GitHub Actions pra alimentar o Resumo Diário (que
lê esse arquivo 1x por dia e manda um WhatsApp único, em vez de cada
automação avisar separado). Se a data guardada no arquivo for de outro dia,
o arquivo é resetado antes de gravar — assim o dia começa "limpo" sozinho,
sem precisar de um passo separado pra zerar.

Uso: python3 scripts/atualizar_status.py <chave> <sucesso|falha> [--contagens caminho.json]
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BRT = timezone(timedelta(hours=-3))
CAMINHO_STATUS = Path("status/hoje.json")


def main():
    if len(sys.argv) < 3:
        print("Uso: atualizar_status.py <chave> <sucesso|falha> [--contagens caminho.json]")
        sys.exit(1)

    chave = sys.argv[1]
    valor = sys.argv[2]

    caminho_contagens = None
    if "--contagens" in sys.argv:
        caminho_contagens = sys.argv[sys.argv.index("--contagens") + 1]

    hoje = datetime.now(BRT).strftime("%d-%m-%Y")

    try:
        status = json.loads(CAMINHO_STATUS.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        status = {}

    if status.get("data") != hoje:
        status = {"data": hoje}

    status[chave] = valor

    if caminho_contagens:
        try:
            status["pbi_contagens"] = json.loads(Path(caminho_contagens).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"Aviso: não consegui ler {caminho_contagens}, seguindo sem contagens.")

    CAMINHO_STATUS.parent.mkdir(parents=True, exist_ok=True)
    CAMINHO_STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Status atualizado: {chave}={valor}")


if __name__ == "__main__":
    main()
