#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de automação — Relatório de Agendamentos (Tableau / AmorSaúde)

O que ele faz:
  1. Faz login no Tableau Online (via Microsoft/Azure AD)
  2. Navega até Relatórios Medicina > Agendamentos > Agendamentos
  3. Preenche o período (sempre do 1º ao último dia do mês escolhido)
  4. Exporta o crosstab, salva localmente e envia ao Google Drive

Como rodar:
    python tableau_agendamentos.py
    python tableau_agendamentos.py --mes 8 --ano 2026
    python tableau_agendamentos.py --headless

Credenciais via variáveis de ambiente (GitHub Secrets):
    TABLEAU_EMAIL
    TABLEAU_SENHA

⚠️ Importante: o login passa pela tela de autenticação da Microsoft (Azure AD).
Se a conta tiver MFA (autenticação multifator) ativo, a automação vai travar
em modo headless no GitHub Actions, pois não há como responder ao código MFA
automaticamente. Veja o README desta pasta para orientações.
"""

import os
import sys
import calendar
import argparse
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from gdrive_utils import upload_file

# ============================================================
# CONFIGURAÇÃO
# ============================================================
ANO_PADRAO = datetime.now().year
MES_PADRAO = datetime.now().month
CAMINHO_PADRAO = str(Path(__file__).parent / "downloads")

EMAIL = os.environ.get("TABLEAU_EMAIL")
SENHA = os.environ.get("TABLEAU_SENHA")
GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_TABLEAU_ID")

TABLEAU_URL = "https://us-east-1.online.tableau.com/#/site/amorsaude/explore"
URL_RELATORIOS_MEDICINA = "/#/site/amorsaude/projects/2166170"
URL_WORKBOOK_AGENDAMENTOS = "/#/site/amorsaude/workbooks/4154113"
URL_VIEW_AGENDAMENTOS = "/#/site/amorsaude/redirect_to_view/22754738"


def calcular_periodo(ano: int, mes: int):
    primeiro_dia = datetime(ano, mes, 1)
    ultimo_dia_num = calendar.monthrange(ano, mes)[1]
    ultimo_dia = datetime(ano, mes, ultimo_dia_num)
    return primeiro_dia.strftime("%d/%m/%Y"), ultimo_dia.strftime("%d/%m/%Y")


def localizar_contexto_rapido(page, selector: str, timeout: int = 15000):
    """
    Varre a página principal e todos os iframes 5 vezes por segundo.
    Retorna o contexto imediatamente assim que o elemento fica visível,
    eliminando os atrasos de timeout.
    """
    start_time = time.time()

    while (time.time() - start_time) < (timeout / 1000.0):
        if page.locator(selector).first.is_visible():
            return page

        for frame in page.frames:
            if frame.locator(selector).first.is_visible():
                return frame

        page.wait_for_timeout(200)

    raise RuntimeError(f"Elemento não encontrado a tempo: {selector}")


def preencher_data(contexto, selector: str, valor: str):
    campo = contexto.locator(selector).first
    campo.fill(valor)
    campo.press("Tab")


def main():
    parser = argparse.ArgumentParser(description="Extrai relatório de Agendamentos do Tableau")
    parser.add_argument("--mes", type=int, default=MES_PADRAO, help="Mês do relatório (1-12)")
    parser.add_argument("--ano", type=int, default=ANO_PADRAO, help="Ano do relatório")
    parser.add_argument("--headless", action="store_true", help="Executa o navegador em modo invisível (headless)")
    parser.add_argument("--destino", type=str, default=CAMINHO_PADRAO, help="Caminho local onde a pasta com a data de hoje será criada e o arquivo será salvo antes do upload")
    args = parser.parse_args()

    if not EMAIL or not SENHA:
        raise RuntimeError(
            "Credenciais não configuradas. Defina as variáveis de ambiente TABLEAU_EMAIL e "
            "TABLEAU_SENHA (no GitHub Actions, configure os Secrets com esses nomes)."
        )

    data_inicial, data_final = calcular_periodo(args.ano, args.mes)
    data_hoje = datetime.now().strftime("%d-%m-%Y")

    pasta_downloads = os.path.join(args.destino, data_hoje)
    os.makedirs(pasta_downloads, exist_ok=True)
    nome_arquivo_base = "Agendamentos"

    print(f"Período do relatório: {data_inicial} até {data_final}")
    print(f"Será salvo localmente em: {pasta_downloads} e enviado ao Google Drive")
    print(f"Modo Headless: {'Ativado' if args.headless else 'Desativado'}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=args.headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"] if args.headless else [],
        )
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        try:
            # --- 1. Tela de login do Tableau ---
            print("Abrindo Tableau...")
            page.goto(TABLEAU_URL)
            page.wait_for_selector("#email", timeout=30000)
            page.fill("#email", EMAIL)
            page.click("#login-submit")

            # --- 2. Login Microsoft — e-mail ---
            page.wait_for_selector("#i0116", timeout=30000)
            page.fill("#i0116", EMAIL)
            page.click("#idSIButton9")

            # --- 3. Login Microsoft — senha ---
            page.wait_for_selector("#i0118", timeout=30000)
            page.fill("#i0118", SENHA)
            page.click("#idSIButton9")

            # --- 4. "Manter sessão iniciada?" ---
            try:
                page.wait_for_selector("#idBtn_Back", timeout=25000)
                page.click("#idBtn_Back")
            except PlaywrightTimeoutError:
                print("A tela de 'manter sessão iniciada' não apareceu ou exigiu MFA.")
                if not args.headless and sys.stdin.isatty():
                    input("Se houver tela de MFA, complete manualmente e pressione ENTER aqui para continuar...")
                else:
                    print("Aviso: Possível bloqueio de MFA em modo headless.")

            # --- 5. Navegar: Relatórios Medicina ---
            print("Acessando relatórios...")
            page.wait_for_selector(f"a[href='{URL_RELATORIOS_MEDICINA}']", timeout=30000)
            page.click(f"a[href='{URL_RELATORIOS_MEDICINA}']")

            # --- 6. Agendamentos (workbook) ---
            page.wait_for_selector(f"a[href='{URL_WORKBOOK_AGENDAMENTOS}']", timeout=30000)
            page.click(f"a[href='{URL_WORKBOOK_AGENDAMENTOS}']")

            # --- 7. Agendamentos (view) ---
            page.wait_for_selector(f"a[href='{URL_VIEW_AGENDAMENTOS}']", timeout=30000)
            page.click(f"a[href='{URL_VIEW_AGENDAMENTOS}']")

            # --- 8. Preencher Data Inicial / Data Final ---
            print("Preenchendo período...")
            contexto_data_ini = localizar_contexto_rapido(page, "textarea[aria-label='Data Inicial']", timeout=30000)
            preencher_data(contexto_data_ini, "textarea[aria-label='Data Inicial']", data_inicial)

            contexto_data_fim = localizar_contexto_rapido(page, "textarea[aria-label='Data Final']", timeout=30000)
            preencher_data(contexto_data_fim, "textarea[aria-label='Data Final']", data_final)

            # --- 9. Espera o relatório recalcular no servidor ---
            print("Aguardando Tableau processar os dados...")
            page.wait_for_timeout(8000)

            # --- 10. Clicar no ícone de download/exportar ---
            print("Abrindo opção de exportar...")
            seletor_icone = "image.tab-button-zone-image"
            contexto_botao = localizar_contexto_rapido(page, seletor_icone, timeout=45000)
            contexto_botao.locator(seletor_icone).first.click(force=True)

            page.wait_for_timeout(3000)

            # --- 11. Clicar em "Baixar" na janela que abre ---
            print("Baixando arquivo...")
            seletor_baixar = "button[data-tb-test-id='export-crosstab-export-Button']"
            contexto_baixar = localizar_contexto_rapido(page, seletor_baixar, timeout=45000)

            with page.expect_download(timeout=60000) as download_info:
                contexto_baixar.locator(seletor_baixar).first.click(force=True)
            download = download_info.value

            extensao = os.path.splitext(download.suggested_filename)[1] or ".csv"
            nome_arquivo = f"{nome_arquivo_base}{extensao}"
            caminho_final = os.path.join(pasta_downloads, nome_arquivo)
            download.save_as(caminho_final)

            print(f"Arquivo salvo localmente em: {caminho_final}")

            upload_file(caminho_final, GDRIVE_FOLDER_ID, filename=nome_arquivo)

        except Exception as erro:
            print(f"Ocorreu um erro: {erro}")
            screenshot_path = os.path.join(pasta_downloads, "erro_screenshot.png")
            try:
                page.screenshot(path=screenshot_path)
                print(f"Print da tela no momento do erro salvo em: {screenshot_path}")
            except Exception:
                pass
            raise
        finally:
            browser.close()

if __name__ == "__main__":
    main()
