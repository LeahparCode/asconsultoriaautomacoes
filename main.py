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

LOGIN = os.getenv("EVO_LOGIN")
SENHA = os.getenv("EVO_SENHA")
GOOGLE_JSON = os.getenv("GOOGLE_DRIVE_CREDENTIALS")
ID_PASTA_DRIVE = "11H5X-G6Bn6K1Ek3hSKWmUuvhaagjpOny"

def upload_to_drive(file_path, file_name):
    try:
        info = json.loads(GOOGLE_JSON)
        creds = service_account.Credentials.from_service_account_info(info)
        service = build('drive', 'v3', credentials=creds)
        
        file_metadata = {
            'name': file_name, 
            'parents': [ID_PASTA_DRIVE]
        }
        media = MediaFileUpload(file_path, resumable=True)
        
        # supportsAllDrives permite que contas de serviço escrevam em pastas de terceiros
        service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id',
            supportsAllDrives=True 
        ).execute()
        return True
    except Exception as e:
        print(f"Erro no upload: {e}")
        return False

def extrair(driver, wait, pasta_download, nome_unidade):
    print(f"Iniciando extração para {nome_unidade}...")
    
    # Espera o Dashboard aparecer (usando um seletor mais flexível)
    xpath_dash = "//div[contains(@class, 'acesso-botao-passo')]//span[contains(text(), 'Dashboard')]"
    dash = wait.until(EC.presence_of_element_located((By.XPATH, xpath_dash)))
    driver.execute_script("arguments[0].scrollIntoView();", dash)
    time.sleep(2)
    driver.execute_script("arguments[0].click();", dash)
    
    print("Abrindo detalhes...")
    detalhes = wait.until(EC.presence_of_element_located((By.ID, "detalhesModalClientesInadimplentes")))
    driver.execute_script("arguments[0].click();", detalhes)
    
    print("Clicando em exportar...")
    export = wait.until(EC.presence_of_element_located((By.XPATH, "//mat-icon[contains(text(), 'get_app')]")))
    driver.execute_script("arguments[0].click();", export)
    
    print("Confirmando...")
    confirm = wait.until(EC.presence_of_element_located((By.ID, "confirmaModalCommon")))
    driver.execute_script("arguments[0].click();", confirm)
    
    print("Aguardando processamento do arquivo (30s)...")
    time.sleep(30) # Aumentado para garantir em arquivos pesados
    
    baixou = False
    for arq in os.listdir(pasta_download):
        if not arq.endswith(('.crdownload', '.tmp')):
            data = datetime.now().strftime("%d-%m-%Y")
            ext = os.path.splitext(arq)[1]
            novo_nome = f"{data}_{nome_unidade}_Clientes{ext}"
            caminho_total = os.path.join(pasta_download, arq)
            if upload_to_drive(caminho_total, novo_nome):
                print(f"✅ Arquivo enviado: {novo_nome}")
                baixou = True
            os.remove(caminho_total)
    
    if not baixou: print("⚠️ Download não detectado na pasta.")
    
    close_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//mat-icon[text()='close']")))
    driver.execute_script("arguments[0].click();", close_btn)
    time.sleep(2)

# Configurações do Chrome
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

temp_dir = os.path.join(os.getcwd(), "downloads")
if not os.path.exists(temp_dir): os.makedirs(temp_dir)

chrome_options.add_experimental_option("prefs", {
    "download.default_directory": temp_dir,
    "download.prompt_for_download": False,
    "directory_upgrade": True,
    "safebrowsing.enabled": True
})

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
wait = WebDriverWait(driver, 40) # Tempo de espera maior para rede instável

try:
    print("Acessando a página de login...")
    driver.get("https://evo5.w12app.com.br/#/acesso/allpfit/autenticacao")
    
    user_input = wait.until(EC.visibility_of_element_located((By.ID, "usuario")))
    pass_input = driver.find_element(By.ID, "senha")
    
    print("Preenchendo credenciais...")
    driver.execute_script(f"arguments[0].value='{LOGIN}'; arguments[0].dispatchEvent(new Event('input', {{ bubbles: true }}));", user_input)
    driver.execute_script(f"arguments[0].value='{SENHA}'; arguments[0].dispatchEvent(new Event('input', {{ bubbles: true }}));", pass_input)
    
    time.sleep(2)
    driver.execute_script("document.querySelector('button[type=submit]').click();")
    
    print("Aguardando redirecionamento para o Dashboard...")
    # Espera até que a URL não contenha mais 'autenticacao'
    wait.until(lambda d: "autenticacao" not in d.current_url)
    time.sleep(10)
    
    extrair(driver, wait, temp_dir, "Salvador")
    
    print("--- Trocando de unidade ---")
    user_menu = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "novo-user-data")))
    driver.execute_script("arguments[0].click();", user_menu)
    
    time.sleep(3)
    select = wait.until(EC.presence_of_element_located((By.TAG_NAME, "mat-select")))
    driver.execute_script("arguments[0].click();", select)
    
    time.sleep(3)
    opcao = wait.until(EC.presence_of_element_located((By.XPATH, "//mat-option[.//div[contains(text(), 'Salvador Pernambues')]]")))
    driver.execute_script("arguments[0].click();", opcao)
    
    print("Aguardando carregamento da nova unidade...")
    time.sleep(12)
    
    extrair(driver, wait, temp_dir, "Pernambues")
    print("🚀 Automação concluída com sucesso!")

except Exception as e:
    print(f"❌ Erro detectado: {e}")
    driver.save_screenshot("debug_error.png") # Isso ajuda se precisar ver a tela do erro
finally:
    driver.quit()
