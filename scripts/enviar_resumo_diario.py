#!/usr/bin/env python3
"""
Lê status/hoje.json (atualizado ao longo do dia pelos outros 4 workflows) e
manda um único resumo no WhatsApp via CallMeBot.

Disparado 1x por dia (09:00 BRT, depois que Gerar Perfil, EVO, PBI e a
1ª execução do Tableau já rodaram) por um job externo no cron-job.org —
veja a seção 7 do README da raiz.
"""
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

NOMES = {
    "gerar_perfil": "Gerar Perfil",
    "evo": "EVO Inadimplentes",
    "pbi": "PBI Export",
    "tableau_primeira_execucao": "Tableau (1ª execução)",
}

ICONES = {"sucesso": "✅", "falha": "❌"}


def montar_mensagem(status: dict) -> str:
    data = status.get("data", "hoje")
    linhas = [f"📊 Resumo do dia {data}"]

    ok = 0
    total = 0
    for chave, nome in NOMES.items():
        valor = status.get(chave)
        if valor is None:
            linhas.append(f"{nome}: ⏳ não rodou (ainda ou hoje não era pra rodar)")
            continue
        total += 1
        if valor == "sucesso":
            ok += 1
        linhas.append(f"{nome}: {ICONES.get(valor, '❓')}")

    contagens = status.get("pbi_contagens")
    if contagens:
        linhas.append(f"  • Inadimplência: {contagens.get('inadimplencia', '?')}")
        linhas.append(f"  • Relacionamento: {contagens.get('relacionamento', '?')}")
        linhas.append(f"  • Vendas: {contagens.get('vendas', '?')}")

    if total:
        linhas.append(f"\nTotal: {ok}/{total} OK")
    else:
        linhas.append("\nNenhuma automação rodou ainda hoje.")

    return "\n".join(linhas)


def enviar_whatsapp(texto: str) -> None:
    phone = os.environ["CALLMEBOT_PHONE"]
    apikey = os.environ["CALLMEBOT_APIKEY"]
    query = urllib.parse.urlencode({"phone": phone, "apikey": apikey, "text": texto})
    url = f"https://api.callmebot.com/whatsapp.php?{query}"
    with urllib.request.urlopen(url, timeout=30) as resposta:
        print(resposta.read().decode("utf-8", errors="replace"))


def main():
    caminho = Path("status/hoje.json")
    try:
        status = json.loads(caminho.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        status = {}

    mensagem = montar_mensagem(status)
    print(mensagem)
    enviar_whatsapp(mensagem)


if __name__ == "__main__":
    main()
