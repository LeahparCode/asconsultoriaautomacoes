import os
import time
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ================= CONFIGURAÇÕES (SECRETS) =================
LOGIN = os.getenv("EVO_LOGIN")
SENHA = os.getenv("EVO_SENHA")
GOOGLE_JSON = os.getenv("GOOGLE_DRIVE_CREDENTIALS")
ID_PASTA_DRIVE = "11H5X-G6Bn6K1Ek3hSKWmUuvhaagjpOny"

def upload_to_drive(file_path, file_name):
    """Faz o upload do arquivo para o Google Drive tratando erros de cota."""
    try:
        info = json.loads(GOOGLE_JSON)
        creds = service_account.Credentials.from_service_account_info(info)
        service = build('drive', 'v3', credentials=creds)
        
        file_metadata = {
            'name': file_name, 
            'parents': [ID_PASTA_DRIVE]
        }
        media = MediaFileUpload(file_path, resumable=True)
        
        # supportsAllDrives=True é essencial para Contas de Serviço em pastas compartilhadas
        service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id',
            supportsAllDrives=True 
        ).execute()
        return True
    except Exception as e:
        print(f"❌ Erro no upload para o Drive: {e}")
        return False

def extrair(driver, wait, pasta_download, nome_unidade):
    """Executa o fluxo de exportação de inadimplentes para a unidade atual."""
    print(f"--- Iniciando extração para: {nome_unidade} ---")
    
    # 1. Dashboard
    xpath_dash = "//div[contains(@class, 'acesso-botao-passo')]//span[contains(text(), 'Dashboard')]"
    dash = wait.until(EC.presence_of_element_located((By.XPATH, xpath_dash)))
    driver.execute_script("arguments[0].scrollIntoView();", dash)
    time.sleep(2)
    driver.execute_script("arguments[0].click();", dash)
    
    # 2. Detalhes Inadimplentes
    print("Abrindo detalhes...")
    detalhes = wait.until(EC.presence_of_element_located((By.ID, "detalhesModalClientesInadimplentes")))
    driver.execute_script("arguments[0].click();", detalhes)
    
    # 3. Ícone de Download
    print("Clicando em exportar...")
    export = wait.until(EC.presence_of_element_located((By.XPATH, "//mat-icon[contains(text(), 'get_app')]")))
    driver.execute_script("arguments[0].click();", export)
    
    # 4. Botão Confirmar no Modal
    print("Confirmando exportação...")
    confirm = wait.until(EC.presence_of_element_located((By.ID, "confirmaModalCommon")))
    driver.execute_script("arguments[0].click();", confirm)
    
    # 5. Espera de Download
    print("Aguardando processamento e download (30s)...")
    time.sleep(30) 
    
    baixou = False
    for arq in os.listdir(pasta_download):
        if not arq.endswith(('.crdownload', '.tmp')):
            data = datetime.now().strftime("%d-%m-%Y")
            ext = os.path.splitext(arq)[1]
            novo_nome = f"{data}_{nome_unidade}_Clientes{ext}"
            caminho_total = os.path.join(pasta_download, arq)
            
            if upload_to_drive(caminho_total, novo_nome):
                print(f"✅ Arquivo enviado ao Drive: {novo_nome}")
                baixou = True
            
            # Limpa a pasta temporária do GitHub
            os.remove(caminho_total)
    
    if not baixou: print("⚠️ Alerta: Nenhum arquivo de download detectado.")
    
    # 6. Fechar Modal
    close_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//mat-icon[text()='close']")))
    driver.execute_script("arguments[0].click();", close_btn)
    time.sleep(3)

# ================= CONFIGURAÇÃO DO BROWSER =================
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# Pasta temporária para downloads no servidor Linux do GitHub
temp_dir = os.path.join(os.getcwd(), "downloads")
if not os.path.exists(temp_dir): os.makedirs(temp_dir)

chrome_options.add_experimental_option("prefs", {
    "download.default_directory": temp_dir,
    "download.prompt_for_download": False,
    "directory_upgrade": True,
    "safebrowsing.enabled": True
})

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
wait = WebDriverWait(driver, 40) # Espera generosa para ambientes cloud

# ================= EXECUÇÃO PRINCIPAL =================
try:
    print("Acessando a página de login...")
    driver.get("https://evo5.w12app.com.br/#/acesso/allpfit/autenticacao")
    
    user_input = wait.until(EC.visibility_of_element_located((By.ID, "usuario")))
    pass_input = driver.find_element(By.ID, "senha")
    
    print("Preenchendo credenciais...")
    # Dispara eventos de input e change para garantir que o Angular valide os campos
    js_fill = "arguments[0].value=arguments[1]; arguments[0].dispatchEvent(new Event('input', { bubbles: true })); arguments[0].dispatchEvent(new Event('change', { bubbles: true }));"
    driver.execute_script(js_fill, user_input, LOGIN)
    driver.execute_script(js_fill, pass_input, SENHA)
    
    time.sleep(2)
    print("Clicando no botão de login...")
    botao_entrar = driver.find_element(By.XPATH, "//button[contains(translate(., 'ENTRAR', 'entrar'), 'entrar') or @type='submit']")
    driver.execute_script("arguments[0].click();", botao_entrar)
    
    print("Aguardando login e redirecionamento...")
    # Aguarda sair da tela de autenticação
    try:
        wait.until(lambda d: "autenticacao" not in d.current_url)
    except:
        print(f"⚠️ Timeout no redirecionamento. URL atual: {driver.current_url}")
        raise
    
    time.sleep(10)
    
    # --- PRIMEIRA UNIDADE (Salvador) ---
    extrair(driver, wait, temp_dir, "Salvador")
    
    # --- TROCA DE UNIDADE ---
    print("Trocando de unidade para Pernambués...")
    user_menu = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "novo-user-data")))
    driver.execute_script("arguments[0].click();", user_menu)
    
    time.sleep(3)
    select = wait.until(EC.presence_of_element_located((By.TAG_NAME, "mat-select")))
    driver.execute_script("arguments[0].click();", select)
    
    time.sleep(3)
    opcao = wait.until(EC.presence_of_element_located((By.XPATH, "//mat-option[.//div[contains(text(), 'Salvador Pernambues')]]")))
    driver.execute_script("arguments[0].click();", opcao)
    
    print("Aguardando carregamento da nova unidade...")
    time.sleep(15)
    
    # --- SEGUNDA UNIDADE (Pernambues) ---
    extrair(driver, wait, temp_dir, "Pernambues")

    print("🚀 Automação finalizada com sucesso total!")

except Exception as e:
    print(f"❌ Erro crítico detectado: {e}")
    # Salva foto da tela para debug no GitHub Artifacts
    driver.save_screenshot("debug_error.png")
    # Levanta o erro para o GitHub Actions marcar como falha
    exit(1)

finally:
    driver.quit()
