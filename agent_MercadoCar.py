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



# Cria o serviço automaticamente
service = Service(os.path.join(os.getcwd(), "chromedriver.exe"))

# Inicia o navegador
driver = webdriver.Chrome(service=service)
#tempo de espera para o carregamento dos elementos
wait = WebDriverWait(driver, 10)

driver.maximize_window() 
# Abre um site
driver.get("https://www.mercadocar.com.br")

# Mantém aberto por 10 segundos


botao = wait.until(
    EC.element_to_be_clickable((By.XPATH, "//button[@id='eu-cookie-ok']"))
)

botao.click()

time.sleep(0.5)

# Encontra o campo de busca e insere o termo "carro"
campo_busca = wait.until(
    EC.presence_of_element_located((By.XPATH, "//*[@id='small-searchterms']"))
)
campo_busca.send_keys("Filtro de bateria")

#clica no enter
botao_busca = wait.until(
    EC.element_to_be_clickable((By.XPATH, "//*[@id='small-search-box-form']/button"))
)
botao_busca.click()

time.sleep(5)

#botâo para exibir todas as marcas
botao_exibir_todas = wait.until(
    EC.element_to_be_clickable((By.XPATH, "//*[@id='showMoreManufacturers']"))
)
botao_exibir_todas.click()

# selecionar a marca "Moura"
marca_moura = wait.until(
    EC.element_to_be_clickable((By.XPATH, "//*[@id='attribute-manufacturer-MOURA (35)']"))
)
marca_moura.click()

time.sleep(5)


# selecionar o ordem de exibição "Menor preço"
selecionar_ordem = wait.until(
    EC.element_to_be_clickable((By.XPATH, "//*[@id='products-orderby']"))
)
selecionar_ordem.click()

ordem_menor_preco = wait.until(
    EC.element_to_be_clickable((By.XPATH, "//*[@id='products-orderby']/option[5]"))
)
ordem_menor_preco.click()

# Fecha o navegador
driver.quit()