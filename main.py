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
        file_metadata = {'name': file_name, 'parents': [ID_PASTA_DRIVE]}
        media = MediaFileUpload(file_path, resumable=True)
        service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return True
    except Exception as e:
        print(f"Erro no upload: {e}")
        return False

def extrair(driver, wait, pasta_download, nome_unidade):
    print(f"Iniciando extração para {nome_unidade}...")
    # Aguarda o dashboard estar clicável
    wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Dashboard']/parent::div"))).click()
    
    # Aguarda o botão de detalhes
    wait.until(EC.element_to_be_clickable((By.ID, "detalhesModalClientesInadimplentes"))).click()
    
    # Aguarda o ícone de exportação
    wait.until(EC.element_to_be_clickable((By.XPATH, "//mat-icon[contains(text(), 'get_app')]"))).click()
    
    # Botão confirmar exportação
    wait.until(EC.element_to_be_clickable((By.ID, "confirmaModalCommon"))).click()
    
    print("Aguardando download...")
    time.sleep(20) # Tempo extra para segurança na nuvem
    
    for arq in os.listdir(pasta_download):
        if not arq.endswith(('.crdownload', '.tmp')):
            data = datetime.now().strftime("%d-%m-%Y")
            ext = os.path.splitext(arq)[1]
            novo_nome = f"{data}_{nome_unidade}_Clientes{ext}"
            caminho_total = os.path.join(pasta_download, arq)
            if upload_to_drive(caminho_total, novo_nome):
                print(f"✅ Sucesso: {novo_nome}")
            os.remove(caminho_total)
    
    wait.until(EC.element_to_be_clickable((By.XPATH, "//mat-icon[text()='close']"))).click()

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
wait = WebDriverWait(driver, 30) # Aumentado para 30 segundos

try:
    print("Acessando o site...")
    driver.get("https://evo5.w12app.com.br/#/acesso/allpfit/autenticacao")
    
    # Espera explícita com seletor robusto para o login
    print("Aguardando campo de login...")
    user_input = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input#usuario, input[name='usuario']")))
    pass_input = driver.find_element(By.CSS_SELECTOR, "input#senha, input[name='senha']")
    
    print("Preenchendo credenciais...")
    driver.execute_script(f"arguments[0].value='{LOGIN}'; arguments[0].dispatchEvent(new Event('input', {{ bubbles: true }}));", user_input)
    driver.execute_script(f"arguments[0].value='{SENHA}'; arguments[0].dispatchEvent(new Event('input', {{ bubbles: true }}));", pass_input)
    
    time.sleep(2)
    driver.execute_script("document.querySelector('button[type=submit]').click();")
    
    print("Aguardando carregamento pós-login...")
    time.sleep(15)
    
    extrair(driver, wait, temp_dir, "Salvador")
    
    print("Trocando de unidade...")
    wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "novo-user-data"))).click()
    time.sleep(2)
    wait.until(EC.element_to_be_clickable((By.TAG_NAME, "mat-select"))).click()
    time.sleep(2)
    wait.until(EC.element_to_be_clickable((By.XPATH, "//mat-option[.//div[contains(text(), 'Salvador Pernambues')]]"))).click()
    
    time.sleep(10)
    extrair(driver, wait, temp_dir, "Pernambues")
    print("Processo finalizado com sucesso!")

except Exception as e:
    print(f"❌ Ocorreu um erro: {e}")
    # Tira um print da tela para ajudar no diagnóstico se der erro de novo
    driver.save_screenshot("erro_screenshot.png")

finally:
    driver.quit()
