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
        
        # O segredo para evitar erro de cota em Contas de Serviço é não pedir campos extras de retorno
        service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id',
            supportsAllDrives=True # Suporte para pastas compartilhadas
        ).execute()
        return True
    except Exception as e:
        print(f"Erro no upload: {e}")
        return False

def extrair(driver, wait, pasta_download, nome_unidade):
    print(f"Iniciando extração para {nome_unidade}...")
    # Clique no Dashboard via JS para evitar interceptação
    dash = wait.until(EC.presence_of_element_located((By.XPATH, "//span[text()='Dashboard']/parent::div")))
    driver.execute_script("arguments[0].click();", dash)
    
    detalhes = wait.until(EC.presence_of_element_located((By.ID, "detalhesModalClientesInadimplentes")))
    driver.execute_script("arguments[0].click();", detalhes)
    
    export = wait.until(EC.presence_of_element_located((By.XPATH, "//mat-icon[contains(text(), 'get_app')]")))
    driver.execute_script("arguments[0].click();", export)
    
    confirm = wait.until(EC.presence_of_element_located((By.ID, "confirmaModalCommon")))
    driver.execute_script("arguments[0].click();", confirm)
    
    print("Aguardando download...")
    time.sleep(20) 
    
    baixou = False
    for arq in os.listdir(pasta_download):
        if not arq.endswith(('.crdownload', '.tmp')):
            data = datetime.now().strftime("%d-%m-%Y")
            ext = os.path.splitext(arq)[1]
            novo_nome = f"{data}_{nome_unidade}_Clientes{ext}"
            caminho_total = os.path.join(pasta_download, arq)
            if upload_to_drive(caminho_total, novo_nome):
                print(f"✅ Sucesso: {novo_nome}")
                baixou = True
            os.remove(caminho_total)
    
    if not baixou: print("⚠️ Nenhum arquivo encontrado para upload.")
    
    close_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//mat-icon[text()='close']")))
    driver.execute_script("arguments[0].click();", close_btn)

# Configurações do Chrome
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

temp_dir = os.path.join(os.getcwd(), "downloads")
os.makedirs(temp_dir, exist_ok=True)
chrome_options.add_experimental_option("prefs", {"download.default_directory": temp_dir})

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
wait = WebDriverWait(driver, 30)

try:
    print("Acessando o site...")
    driver.get("https://evo5.w12app.com.br/#/acesso/allpfit/autenticacao")
    
    user_input = wait.until(EC.visibility_of_element_located((By.ID, "usuario")))
    pass_input = driver.find_element(By.ID, "senha")
    
    print("Preenchendo credenciais...")
    driver.execute_script(f"arguments[0].value='{LOGIN}'; arguments[0].dispatchEvent(new Event('input', {{ bubbles: true }}));", user_input)
    driver.execute_script(f"arguments[0].value='{SENHA}'; arguments[0].dispatchEvent(new Event('input', {{ bubbles: true }}));", pass_input)
    
    time.sleep(2)
    driver.execute_script("document.querySelector('button[type=submit]').click();")
    
    print("Aguardando carregamento pós-login...")
    time.sleep(15)
    
    extrair(driver, wait, temp_dir, "Salvador")
    
    print("Trocando de unidade...")
    user_menu = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "novo-user-data")))
    driver.execute_script("arguments[0].click();", user_menu)
    
    time.sleep(3)
    # Clique forçado no mat-select para ignorar sobreposição
    select = wait.until(EC.presence_of_element_located((By.TAG_NAME, "mat-select")))
    driver.execute_script("arguments[0].click();", select)
    
    time.sleep(3)
    opcao = wait.until(EC.presence_of_element_located((By.XPATH, "//mat-option[.//div[contains(text(), 'Salvador Pernambues')]]")))
    driver.execute_script("arguments[0].click();", opcao)
    
    time.sleep(10)
    extrair(driver, wait, temp_dir, "Pernambues")
    print("🚀 Processo finalizado com sucesso!")

except Exception as e:
    print(f"❌ Ocorreu um erro: {e}")
finally:
    driver.quit()
