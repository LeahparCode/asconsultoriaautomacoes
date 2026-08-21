#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Automação - EVO (AllpFit) - Extração de Clientes Inadimplentes
Versão GitHub Actions

Diferenças em relação à versão original (uso local com Google Drive Desktop):
    - Login/senha vêm de variáveis de ambiente (Secrets), não ficam no código.
    - Os arquivos são salvos primeiro numa pasta local temporária (./downloads)
      e depois enviados ao Google Drive via API (Service Account). O upload é
      "best-effort": se falhar, o arquivo continua disponível como artefato
      do GitHub Actions.

Requisitos:
    pip install -r requirements.txt
    playwright install --with-deps chrome
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from gdrive_utils import upload_file

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

# ================= CONFIGURAÇÕES =================
# O EVO redireciona entre hosts (em 21/08/2026 o log mostrou a navegação indo
# de "evo-abc-sec" para "evo-abc-3" no meio do login). Se a W12 trocar de host
# de novo, dá pra repontar sem mexer no código, pelo Secret/variável EVO_URL.
# `or` em vez do default do .get(): no GitHub Actions, um secret que não existe
# chega como string vazia (não como variável ausente), e o .get() devolveria "".
URL_DO_SITE = (
    os.environ.get("EVO_URL")
    or "https://evo-abc-sec.w12app.com.br/#/acesso/allpfit/autenticacao"
)
ROTA_LOGIN = "/acesso/"  # trecho da URL que indica que ainda estamos na tela de autenticação
LOGIN = os.environ.get("EVO_LOGIN")
SENHA = os.environ.get("EVO_SENHA")
HEADLESS_MODE = os.environ.get("EVO_HEADLESS", "true").lower() != "false"

DOWNLOAD_DIR = Path(__file__).parent / "downloads"
GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_EVO_ID")

TIMEOUT_MS = 25_000
TIMEOUT_PRIMEIRA_CARGA_MS = 60_000  # a primeira carga do Angular costuma ser mais lenta
TIMEOUT_DADOS_MS = 60_000  # elementos que dependem de dados vindos do backend (ex: contagem de inadimplentes)
TIMEOUT_NETWORKIDLE_MS = 20_000  # espera a rede "acalmar" antes de contar o timeout do elemento de dados
TIMEOUT_REDIRECT_MS = 30_000  # espera os redirecionamentos de host pararem antes de digitar no formulário
TIMEOUT_LOGIN_MS = 30_000  # espera o login ser aceito (sair da rota de autenticação)
TENTATIVAS_LOGIN = 3  # o formulário Angular às vezes não registra a 1ª digitada; repetir resolve
MAX_TENTATIVAS_POR_UNIDADE = 2  # 1 tentativa original + 1 retry (refazendo o login, se preciso)
# ===================================================


def _texto_erro_login(page):
    """Tenta capturar a mensagem que o EVO mostra na tela quando o login é recusado."""
    for seletor in ["mat-error", ".mat-error", "[class*='toast']", "[class*='alert']"]:
        try:
            for elemento in page.query_selector_all(seletor):
                if elemento.is_visible():
                    texto = (elemento.inner_text() or "").strip()
                    if texto:
                        return texto
        except Exception:
            continue
    return ""


def esperar_url_estabilizar(page, timeout_ms=TIMEOUT_REDIRECT_MS):
    """
    Espera a URL parar de mudar.

    O EVO faz um redirecionamento de host logo depois de abrir a página. Se o
    formulário for preenchido antes desse redirecionamento terminar, o que foi
    digitado vai junto com a página descartada e a aplicação reaparece na tela
    de login — foi exatamente isso que quebrou a execução de 21/08/2026.
    """
    limite = time.monotonic() + timeout_ms / 1000
    anterior = page.url
    estavel_desde = time.monotonic()
    while time.monotonic() < limite:
        page.wait_for_timeout(500)
        atual = page.url
        if atual != anterior:
            print(f"  ↪ redirecionado para: {atual}")
            anterior = atual
            estavel_desde = time.monotonic()
        elif time.monotonic() - estavel_desde >= 2:
            break
    return page.url


def _digitar(campo, texto):
    """Digita tecla a tecla. press_sequentially é o nome novo (Playwright >= 1.38)."""
    if hasattr(campo, "press_sequentially"):
        campo.press_sequentially(texto, delay=25)
    else:  # compatibilidade com versões antigas, caso alguém rode localmente
        campo.type(texto, delay=25)


def _preencher_credenciais(page):
    """
    Preenche usuário e senha e devolve o botão "entrar".

    Chamar page.fill() logo que o campo aparece no DOM não basta: o formulário é
    Angular, e enquanto ele não termina de se inicializar o valor entra no campo
    mas não chega ao modelo da aplicação. O "entrar" então submete um formulário
    vazio, e a tela de login continua ali sem exibir erro nenhum.

    Na execução de 21/08/2026 dava pra ver isso pelo relógio: as tentativas que
    preencheram o formulário em 0,3s e 1,1s falharam, e a que levou 3,7s (ou
    seja, esperou o formulário ficar pronto) passou.
    """
    campo_usuario = page.locator("input#usuario")
    campo_senha = page.locator("input#senha")
    botao = page.locator("button:has-text('entrar')")

    campo_usuario.wait_for(state="visible", timeout=TIMEOUT_PRIMEIRA_CARGA_MS)
    campo_senha.wait_for(state="visible", timeout=TIMEOUT_MS)
    botao.wait_for(state="visible", timeout=TIMEOUT_MS)

    # Dá tempo do Angular terminar de amarrar o formulário antes de digitar.
    try:
        page.wait_for_load_state("networkidle", timeout=TIMEOUT_NETWORKIDLE_MS)
    except PlaywrightTimeoutError:
        pass

    for tentativa in range(1, 4):
        campo_usuario.fill("")
        _digitar(campo_usuario, LOGIN)
        campo_senha.fill("")
        _digitar(campo_senha, SENHA)

        if campo_usuario.input_value() == LOGIN and campo_senha.input_value() == SENHA:
            return botao

        print(f"  ⚠️  O formulário não reteve o que foi digitado ({tentativa}/3); repetindo...")
        page.wait_for_timeout(1500)

    raise RuntimeError(
        "Não foi possível preencher o formulário de login: os campos não retêm o "
        "valor digitado (formulário provavelmente não terminou de inicializar)."
    )


def fazer_login(page):
    """Abre o EVO, espera os redirecionamentos, faz login e confirma que ele foi aceito."""
    ultimo_detalhe = ""

    for tentativa in range(1, TENTATIVAS_LOGIN + 1):
        print(f"Abrindo o EVO... (login {tentativa}/{TENTATIVAS_LOGIN})")
        page.goto(URL_DO_SITE, wait_until="domcontentloaded")

        url_estavel = esperar_url_estabilizar(page)
        if url_estavel.split("#")[0].rstrip("/") != URL_DO_SITE.split("#")[0].rstrip("/"):
            print(
                f"⚠️  O EVO redirecionou para outro endereço: {url_estavel}\n"
                f"   (configurado: {URL_DO_SITE})\n"
                "   Se esse novo endereço virar o definitivo, aponte a variável EVO_URL pra ele."
            )

        print("Preenchendo o formulário de login...")
        botao = _preencher_credenciais(page)
        botao.click()

        # botao.click() só dispara o clique, não espera o login terminar. Sem esta
        # confirmação o script seguia direto pro dashboard e ficava 60s esperando um
        # elemento que nunca ia aparecer, porque continuava na tela de login — e o
        # erro final culpava "unidade sem inadimplentes", que não era o problema.
        print("Confirmando que o login foi aceito...")
        try:
            page.wait_for_function(
                f"() => !location.href.includes({ROTA_LOGIN!r})", timeout=TIMEOUT_LOGIN_MS
            )
        except PlaywrightTimeoutError:
            ultimo_detalhe = _texto_erro_login(page)
            print(
                f"⚠️  Login {tentativa}/{TENTATIVAS_LOGIN} não completou — a aplicação "
                f"continua em {page.url}."
                + (f" Mensagem na tela: {ultimo_detalhe!r}." if ultimo_detalhe else "")
            )
            if tentativa < TENTATIVAS_LOGIN:
                page.wait_for_timeout(3000)
            continue

        print(f"✅ Login concluído. URL atual: {page.url}")
        return

    raise RuntimeError(
        f"Login não foi concluído após {TENTATIVAS_LOGIN} tentativas: a aplicação "
        f"continua na tela de autenticação ({page.url}). "
        + (
            f"Mensagem exibida na tela: {ultimo_detalhe!r}."
            if ultimo_detalhe
            else "Nenhuma mensagem de erro visível na tela — pode ser credencial "
            "inválida/expirada, bloqueio por excesso de tentativas, ou mudança "
            "no fluxo de login do EVO."
        )
    )

    print(f"✅ Login concluído. URL atual: {page.url}")


def extrair_dados_inadimplentes(page, nome_desejado, timeout_dados=TIMEOUT_DADOS_MS):
    """Abre o quadro de inadimplentes, exporta, salva localmente e envia ao Drive."""
    print("Acessando o Dashboard...")
    page.wait_for_selector(
        "[data-cy='home-atalho-dashboard']", state="visible", timeout=TIMEOUT_PRIMEIRA_CARGA_MS
    )
    page.click("[data-cy='home-atalho-dashboard']")

    # Dá uma chance da rede "acalmar" antes de começar a contar o timeout do dado em si.
    # Isso evita que lentidão de rede consuma o tempo destinado à espera do elemento.
    try:
        page.wait_for_load_state("networkidle", timeout=TIMEOUT_NETWORKIDLE_MS)
    except PlaywrightTimeoutError:
        print("Aviso: rede ainda ativa após o tempo de espera, seguindo mesmo assim...")

    print("Abrindo detalhes de Inadimplentes (aguardando os dados carregarem)...")
    page.wait_for_selector(
        "#detalhesModalClientesInadimplentes", state="visible", timeout=timeout_dados
    )
    page.click("#detalhesModalClientesInadimplentes")

    print("Clicando no ícone de exportar...")
    page.click("xpath=//mat-icon[contains(text(), 'get_app') and @data-cy='Evogrid-11']")

    print("Confirmando a exportação no modal e aguardando o download...")
    with page.expect_download() as download_info:
        page.click("#confirmaModalCommon")
    download = download_info.value

    # Monta o nome final e salva na pasta local (depois enviada ao Drive).
    # No Drive, o arquivo vai para dentro de uma subpasta com a data do dia
    # (uma subpasta nova por dia). Nome estável (sem data) dentro dela para
    # que, se essa unidade for extraída de novo no mesmo dia, o arquivo já
    # existente na subpasta do dia seja substituído em vez de duplicado.
    extensao = os.path.splitext(download.suggested_filename)[1]
    data_atual = datetime.now().strftime("%d-%m-%Y")
    nome_final = f"{nome_desejado}{extensao}"

    pasta_destino_final = DOWNLOAD_DIR / f"Inadimplentes {data_atual}"
    pasta_destino_final.mkdir(parents=True, exist_ok=True)

    caminho_local = pasta_destino_final / nome_final
    download.save_as(str(caminho_local))
    print(f"✅ Arquivo salvo localmente em: {caminho_local}")

    upload_file(
        str(caminho_local),
        GDRIVE_FOLDER_ID,
        filename=nome_final,
        subfolder_name=f"Inadimplentes {data_atual}",
    )

    print("Fechando o quadro de inadimplentes...")
    page.click("xpath=//mat-icon[text()='close']")


def extrair_com_retry(page, nome_desejado, relogin=None):
    """
    Tenta extrair os dados da unidade. Se der timeout, tenta se recuperar e
    repete uma vez antes de desistir. Retorna True se conseguiu, False se falhou
    mesmo após o retry (permite seguir para a próxima unidade sem abortar tudo).
    """
    for tentativa in range(1, MAX_TENTATIVAS_POR_UNIDADE + 1):
        try:
            extrair_dados_inadimplentes(page, nome_desejado)
            return True
        except PlaywrightTimeoutError as e:
            print(f"⚠️  Tentativa {tentativa}/{MAX_TENTATIVAS_POR_UNIDADE} falhou por timeout: {e}")
            caiu_no_login = ROTA_LOGIN in page.url
            if tentativa < MAX_TENTATIVAS_POR_UNIDADE:
                # Se a sessão caiu pra tela de login, recarregar não resolve —
                # a página recarregada continua sendo a tela de login, e a 2ª
                # tentativa falhava garantido. Nesse caso, refaz o login.
                if caiu_no_login and relogin:
                    print(f"A sessão voltou para a tela de login ({page.url}) — refazendo o login...")
                    relogin()
                else:
                    print("Recarregando a página e tentando novamente...")
                    page.reload()
                    page.wait_for_timeout(3000)
            else:
                nome_print = f"erro_evo_{nome_desejado}_{datetime.now().strftime('%H%M%S')}.png"
                if caiu_no_login:
                    motivo = (
                        f"a aplicação está na tela de login ({page.url}), ou seja, a "
                        f"sessão não se manteve — verifique as credenciais (EVO_LOGIN/"
                        f"EVO_SENHA) e se o endereço do EVO mudou (variável EVO_URL)."
                    )
                else:
                    motivo = (
                        "isso costuma acontecer quando a unidade não tem inadimplentes "
                        "no momento (o quadro não chega a aparecer) ou por instabilidade "
                        "real do site."
                    )
                print(
                    f"❌ [ERRO] Falha definitiva na unidade '{nome_desejado}' após "
                    f"{MAX_TENTATIVAS_POR_UNIDADE} tentativas: {motivo}"
                )
                try:
                    page.screenshot(path=nome_print)
                    print(f"Screenshot salva em: {os.path.abspath(nome_print)}")
                except Exception:
                    pass
                return False
    return False


def iniciar_automacao():
    if not LOGIN or not SENHA:
        raise RuntimeError(
            "Credenciais não configuradas. Defina as variáveis de ambiente EVO_LOGIN e EVO_SENHA "
            "(no GitHub Actions, configure os Secrets com esses nomes)."
        )

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Os arquivos serão salvos localmente em: {DOWNLOAD_DIR} e enviados ao Google Drive.")

    with sync_playwright() as p:
        print("Modo Headless ATIVADO." if HEADLESS_MODE else "Modo Headless DESATIVADO.")
        browser = p.chromium.launch(
            headless=HEADLESS_MODE,
            channel="chrome",  # usa o Google Chrome instalado de verdade, menos detectável que o Chromium puro
            args=[
                "--disable-blink-features=AutomationControlled",
                "--use-gl=swiftshader",
                "--enable-webgl",
                "--disable-gpu-sandbox",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            accept_downloads=True,
            locale="pt-BR",
            timezone_id="America/Bahia",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
        )
        context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt']});
            window.chrome = { runtime: {} };
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters)
            );
            """
        )

        page = context.new_page()
        page.set_default_timeout(TIMEOUT_MS)

        resultados = {}

        try:
            # 1. Acessar o site e logar (já confirmando que o login foi aceito)
            fazer_login(page)

            # 2. Primeira extração (Salvador - BA)
            print("\n--- Iniciando extração da unidade: Salvador - BA ---")
            resultados["Salvador - BA"] = extrair_com_retry(
                page, "Salvador_Clientes", relogin=lambda: fazer_login(page)
            )

            # 3. Trocar de unidade
            print("\n--- Trocando de unidade ---")
            try:
                print("Abrindo menu do usuário...")
                page.click("div.novo-user-data")

                print("Abrindo o dropdown de franquias...")
                page.click("xpath=//mat-select[.//span[contains(text(), 'Salvador - BA - 47')]]")

                print("Selecionando a nova franquia: Pernambués...")
                page.click("xpath=//mat-option[.//div[contains(text(), 'Salvador Pernambues')]]")

                print("Aguardando os dados da nova unidade carregarem...")
                page.wait_for_timeout(4000)

                # 4. Segunda extração (Pernambués)
                print("\n--- Iniciando extração da unidade: Salvador Pernambues - BA ---")
                resultados["Salvador Pernambués - BA"] = extrair_com_retry(
                    page, "Pernambues_Clientes", relogin=lambda: fazer_login(page)
                )
            except Exception as e:
                print(f"❌ [ERRO] Falha ao trocar de unidade para Pernambués: {e}")
                resultados["Salvador Pernambués - BA"] = False

            # 5. Resumo final
            print("\n===== RESUMO DA EXECUÇÃO =====")
            houve_falha = False
            for unidade, sucesso in resultados.items():
                status = "✅ OK" if sucesso else "❌ FALHOU"
                print(f"{unidade}: {status}")
                if not sucesso:
                    houve_falha = True

            if houve_falha:
                print(f"\n⚠️  Execução concluída com pelo menos uma falha. Arquivos disponíveis foram salvos em:\n{DOWNLOAD_DIR}")
                raise RuntimeError("Uma ou mais unidades falharam na extração — veja o resumo acima e o(s) screenshot(s) de erro.")
            else:
                print(f"\n🚀 Sucesso absoluto! Todos os arquivos foram processados:\n{DOWNLOAD_DIR}")

        except PlaywrightTimeoutError as e:
            nome_print = f"erro_evo_{datetime.now().strftime('%H%M%S')}.png"
            print(f"\n❌ [ERRO] O script parou por timeout esperando um elemento:\n{e}\n")
            print(f"Screenshot salva em: {os.path.abspath(nome_print)}")
            page.screenshot(path=nome_print)
            raise
        except Exception as e:
            nome_print = f"erro_evo_{datetime.now().strftime('%H%M%S')}.png"
            print(f"\n❌ [ERRO] O script parou devido ao seguinte problema:\n{e}\n")
            print(f"Screenshot salva em: {os.path.abspath(nome_print)}")
            page.screenshot(path=nome_print)
            raise
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    iniciar_automacao()
