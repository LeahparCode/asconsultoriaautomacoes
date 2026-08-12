"""
Automação - RedeService (Cartão de Todos) - Geração de Perfil
================================================================

Fluxo:
1. Login (usuário + senha)
2. Menu "Processos Diários"
3. Link "Geração de Perfil"
4. Botão "Novo"
5. Checkbox "Selecionar todos"
6. Botão "Iniciar"

Credenciais são lidas de variáveis de ambiente (GitHub Secrets):
    RS_LOGIN
    RS_SENHA
"""

import os
import time

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

URL_LOGIN = "https://cobranca01.redeservice.com.br/cobranca.be.cartaotodos/Home/Login?sessaoInvalida=1"

LOGIN_USUARIO = os.environ.get("RS_LOGIN")
LOGIN_SENHA = os.environ.get("RS_SENHA")

TIMEOUT_MS = 20_000  # 20 segundos


def fazer_login(page):
    page.goto(URL_LOGIN)

    page.fill("#Login", LOGIN_USUARIO)
    page.fill("#PasswordTextBox", LOGIN_SENHA)

    page.click("button[type='submit']:has-text('Entrar')")

    # Espera a página carregar após o login (sem precisar de sleep manual)
    page.wait_for_load_state("networkidle")


def abrir_processos_diarios(page):
    page.click("a:has(span.menu-title:has-text('Processos Diários'))")


def abrir_geracao_perfil(page):
    page.click("a[href='/cobranca.be.cartaotodos/GeraPerfil']")
    page.wait_for_load_state("networkidle")


def clicar_novo(page):
    page.click("#demo-btn-addrow")


def selecionar_todos(page):
    checkbox = page.locator("input[name='btSelectAll']")
    if not checkbox.is_checked():
        checkbox.check()


def clicar_iniciar(page):
    page.click("#iniciar")


def main():
    if not LOGIN_USUARIO or not LOGIN_SENHA:
        raise RuntimeError(
            "Credenciais não configuradas. Defina as variáveis de ambiente RS_LOGIN e RS_SENHA "
            "(no GitHub Actions, configure os Secrets com esses nomes)."
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(TIMEOUT_MS)

        try:
            print("Fazendo login...")
            fazer_login(page)

            print("Abrindo 'Processos Diários'...")
            abrir_processos_diarios(page)

            print("Abrindo 'Geração de Perfil'...")
            abrir_geracao_perfil(page)

            print("Clicando em 'Novo'...")
            clicar_novo(page)

            print("Selecionando todos os itens...")
            selecionar_todos(page)

            print("Clicando em 'Iniciar'...")
            clicar_iniciar(page)

            print("Processo de Geração de Perfil iniciado com sucesso.")
            time.sleep(5)

        except PlaywrightTimeoutError as e:
            print(f"Erro: elemento não encontrado a tempo -> {e}")
            page.screenshot(path="erro_geracao_perfil.png")
            raise
        finally:
            browser.close()


if __name__ == "__main__":
    main()
