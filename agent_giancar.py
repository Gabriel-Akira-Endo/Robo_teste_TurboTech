import selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
import time
import os
import select

#caminho do chromeDriver pro robô
service = Service(os.path.join(os.getcwd(), "chromedriver.exe"))

# Inicia o navegador
driver = webdriver.Chrome(service=service)
#tempo de espera para o carregamento dos elementos
wait = WebDriverWait(driver, 10)

driver.maximize_window() 
# Abre um site
driver.get("http://peca.ai/")

time.sleep(3)

login_start = wait.until(
    EC.presence_of_element_located((By.XPATH, '//*[@id="__next"]/div[2]/header/div[1]/div[2]/div[2]/button'))
)
login_start.click()

time.sleep(8)
# iniciar pesquisa


time.sleep(5)
driver.quit()