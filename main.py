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

# Configurações via Environment Variables (Secrets do GitHub)
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
    # Fluxo de extração (Dashboard -> Detalhes -> Exportar -> Confirmar)
    wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Dashboard']/parent::div"))).click()
    wait.until(EC.element_to_be_clickable((By.ID, "detalhesModalClientesInadimplentes"))).click()
    wait.until(EC.element_to_be_clickable((By.XPATH, "//mat-icon[contains(text(), 'get_app')]"))).click()
    wait.until(EC.element_to_be_clickable((By.ID, "confirmaModalCommon"))).click()
    
    # Espera o download concluir na pasta temporária
    time.sleep(15)
    for arq in os.listdir(pasta_download):
        if not arq.endswith(('.crdownload', '.tmp')):
            data = datetime.now().strftime("%d-%m-%Y")
            novo_nome = f"{data}_{nome_unidade}_Clientes{os.path.splitext(arq)[1]}"
            caminho_total = os.path.join(pasta_download, arq)
            if upload_to_drive(caminho_total, novo_nome):
                print(f"Sucesso: {novo_nome}")
            os.remove(caminho_total)
    
    wait.until(EC.element_to_be_clickable((By.XPATH, "//mat-icon[text()='close']"))).click()

# Configuração do Chrome para Ambiente Cloud (GitHub Actions)
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
temp_dir = os.path.join(os.getcwd(), "downloads")
os.makedirs(temp_dir, exist_ok=True)
chrome_options.add_experimental_option("prefs", {"download.default_directory": temp_dir})

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
wait = WebDriverWait(driver, 20)

try:
    driver.get("https://evo5.w12app.com.br/#/acesso/allpfit/autenticacao")
    # Login via JS para evitar erros de animação mat-form-field
    user_input = wait.until(EC.presence_of_element_located((By.ID, "usuario")))
    pass_input = driver.find_element(By.ID, "senha")
    driver.execute_script(f"arguments[0].value='{LOGIN}'; arguments[0].dispatchEvent(new Event('input'));", user_input)
    driver.execute_script(f"arguments[0].value='{SENHA}'; arguments[0].dispatchEvent(new Event('input'));", pass_input)
    driver.execute_script("document.querySelector('button[type=submit]').click();")
    
    time.sleep(10)
    extrair(driver, wait, temp_dir, "Salvador")
    
    # Troca de Unidade
    wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "novo-user-data"))).click()
    wait.until(EC.element_to_be_clickable((By.TAG_NAME, "mat-select"))).click()
    wait.until(EC.element_to_be_clickable((By.XPATH, "//mat-option[.//div[contains(text(), 'Salvador Pernambues')]]"))).click()
    time.sleep(8)
    
    extrair(driver, wait, temp_dir, "Pernambues")

finally:
    driver.quit()