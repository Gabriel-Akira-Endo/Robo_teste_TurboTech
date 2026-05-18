from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

# Configurar o driver do Chrome
options = webdriver.ChromeOptions()
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

try:
    # Abrir o site
    url = "http://peca.ai/"
    driver.get(url)
    print(f"Navegador aberto em: {url}")
    
    # Aguardar para ver o resultado (5 segundos)
    time.sleep(5)
    
    


except Exception as e:
    print(f"Erro ao abrir o site: {e}")
    
finally:
    # Fechar o navegador
    driver.quit()
    print("Navegador fechado")
