"""
Busca produtos da loja Atlanta no ML com login.
Captura preço com desconto + frete e salva em JSON.

Instalar:
    pip install selenium webdriver-manager beautifulsoup4
"""
import json
import time
import re
from typing import Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# ─────────────────────────────────────────────
# ⚙️  CONFIGURAÇÕES — edite aqui
# ─────────────────────────────────────────────
EMAIL    = "seu_email@gmail.com"     # ← seu e-mail do ML
SENHA    = "sua_senha_aqui"          # ← sua senha do ML
LOJA     = "atlanta"                 # ← slug da loja
QUERY    = "valvula sandero"         # ← produto que quer buscar
PAGINAS  = 1                         # ← quantas páginas raspar (48 produtos cada)
HEADLESS = False                     # ← False = abre janela (recomendado para login)
ARQUIVO  = "resultados.json"         # ← nome do arquivo de saída


# ─────────────────────────────────────────────
# 1. Configura o driver
# ─────────────────────────────────────────────
def setup_driver(headless: bool = False) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,900")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    # Oculta o webdriver do JS
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


# ─────────────────────────────────────────────
# 2. Login no Mercado Livre
# ─────────────────────────────────────────────
def fazer_login(driver: webdriver.Chrome, email: str, senha: str) -> bool:
    print("🔐 Fazendo login no Mercado Livre...")
    driver.get("https://www.mercadolivre.com.br/")
    time.sleep(2)

    try:
        # Clica em "Entrar"
        entrar = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'registration') or contains(text(),'Entrar') or contains(@class,'nav-menu-item-login')]"))
        )
        entrar.click()
        time.sleep(2)
    except TimeoutException:
        # Tenta acessar diretamente a página de login
        driver.get("https://www.mercadolivre.com.br/login")
        time.sleep(2)

    try:
        # Campo e-mail
        campo_email = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "user_id"))
        )
        campo_email.clear()
        campo_email.send_keys(email)
        campo_email.send_keys(Keys.RETURN)
        time.sleep(2)

        # Campo senha
        campo_senha = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "password"))
        )
        campo_senha.clear()
        campo_senha.send_keys(senha)
        campo_senha.send_keys(Keys.RETURN)
        time.sleep(4)

        # Verifica se logou (procura elemento que só aparece logado)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(@href,'myml') or contains(@class,'nav-menu-account')]"))
        )
        print("✅ Login realizado com sucesso!")
        return True

    except TimeoutException:
        print("⚠️  Pode ter aparecido CAPTCHA ou verificação extra.")
        print("   Resolva manualmente na janela do Chrome e pressione ENTER aqui...")
        input("   [ENTER para continuar depois de resolver]")
        return True
    except Exception as e:
        print(f"❌ Erro no login: {e}")
        driver.save_screenshot("erro_login.png")
        print("   Screenshot salvo: erro_login.png")
        return False


# ─────────────────────────────────────────────
# 3. Extrai preço do texto
# ─────────────────────────────────────────────
def extrair_preco(texto: str) -> Optional[float]:
    if not texto:
        return None
    limpo = re.sub(r'[^\d.,]', '', texto)
    if ',' in limpo and '.' in limpo:
        limpo = limpo.replace('.', '').replace(',', '.')
    elif ',' in limpo:
        limpo = limpo.replace(',', '.')
    try:
        return float(limpo)
    except:
        return None


# ─────────────────────────────────────────────
# 4. Raspa os produtos
# ─────────────────────────────────────────────
def raspar_produtos(driver: webdriver.Chrome, slug: str, query: str, paginas: int) -> list:
    resultados = []

    for pagina in range(paginas):
        offset = pagina * 48

        if query:
            url = f"https://lista.mercadolivre.com.br/{query.replace(' ', '-')}_Loja_{slug}"
        else:
            url = f"https://www.mercadolivre.com.br/loja/{slug}/mais-vendidos"

        if offset > 0:
            url += f"_Desde_{offset + 1}"

        print(f"\n🌐 Página {pagina + 1}: {url}")
        driver.get(url)
        time.sleep(3)

        # Scroll para carregar tudo
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        cards = driver.find_elements(By.CSS_SELECTOR, ".ui-search-layout__item")
        if not cards:
            print(f"⚠️  Nenhum produto encontrado na página {pagina + 1}")
            break

        print(f"📦 {len(cards)} produtos encontrados")

        for card in cards:
            try:
                # Título
                try:
                    titulo = card.find_element(By.CSS_SELECTOR, ".poly-component__title").text.strip()
                except NoSuchElementException:
                    titulo = None

                # Preço principal (com desconto se logado)
                try:
                    fracao = card.find_element(By.CSS_SELECTOR, ".andes-money-amount__fraction").text.strip()
                    try:
                        cents = card.find_element(By.CSS_SELECTOR, ".andes-money-amount__cents").text.strip()
                    except NoSuchElementException:
                        cents = "00"
                    preco_texto = f"R$ {fracao},{cents}"
                    preco = extrair_preco(preco_texto)
                except NoSuchElementException:
                    preco_texto = None
                    preco = None

                # Preço original (antes do desconto)
                try:
                    preco_original_el = card.find_element(By.CSS_SELECTOR, ".andes-money-amount--previous .andes-money-amount__fraction")
                    preco_original = extrair_preco(preco_original_el.text)
                except NoSuchElementException:
                    preco_original = None

                # Percentual de desconto
                try:
                    desconto_el = card.find_element(By.CSS_SELECTOR, ".andes-money-amount__discount, .poly-price__discount")
                    desconto = desconto_el.text.strip()
                except NoSuchElementException:
                    desconto = None

                # Frete
                try:
                    frete_el = card.find_element(By.CSS_SELECTOR, ".poly-component__shipping")
                    frete_texto = frete_el.text.strip()
                    frete_gratis = "grátis" in frete_texto.lower() or "gratis" in frete_texto.lower()
                except NoSuchElementException:
                    frete_texto = None
                    frete_gratis = False

                # Vendedor
                try:
                    vendedor = card.find_element(By.CSS_SELECTOR, ".poly-component__seller").text.strip()
                except NoSuchElementException:
                    vendedor = None

                # Link
                try:
                    link = card.find_element(By.CSS_SELECTOR, "a.poly-component__title").get_attribute("href")
                except NoSuchElementException:
                    try:
                        link = card.find_element(By.TAG_NAME, "a").get_attribute("href")
                    except NoSuchElementException:
                        link = None

                resultados.append({
                    "titulo":         titulo,
                    "preco":          preco,
                    "preco_texto":    preco_texto,
                    "preco_original": preco_original,
                    "desconto":       desconto,
                    "frete_gratis":   frete_gratis,
                    "frete_texto":    frete_texto,
                    "vendedor":       vendedor,
                    "link":           link,
                    "pagina":         pagina + 1,
                })

            except Exception as e:
                continue

        time.sleep(1.5)

    return resultados


# ─────────────────────────────────────────────
# 5. Exibe no console
# ─────────────────────────────────────────────
def exibir_resultados(resultados: list):
    if not resultados:
        print("\n⚠️  Nenhum produto encontrado.")
        return

    print(f"\n{'='*65}")
    for i, r in enumerate(resultados, 1):
        preco = r["preco_texto"] or "N/A"
        orig  = f"  (era R$ {r['preco_original']:,.2f})".replace(",", "X").replace(".", ",").replace("X", ".") if r["preco_original"] else ""
        desc  = f"  {r['desconto']}" if r["desconto"] else ""
        frete = f"🚚 {r['frete_texto']}" if r["frete_texto"] else "📦 Sem info de frete"

        print(f"\n[{i}] {r['titulo']}")
        print(f"     💰 {preco}{orig}{desc}")
        print(f"     {frete}")
        if r["vendedor"]:
            print(f"     🏪 {r['vendedor']}")
        print(f"     🔗 {r['link']}")

    print(f"\n{'='*65}")
    print(f"Total: {len(resultados)} produtos")


# ─────────────────────────────────────────────
# 6. Salva JSON
# ─────────────────────────────────────────────
def salvar_json(resultados: list, arquivo: str):
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Resultados salvos em '{arquivo}'")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    driver = setup_driver(headless=HEADLESS)

    try:
        logado = fazer_login(driver, EMAIL, SENHA)
        if not logado:
            print("❌ Não foi possível logar. Encerrando.")
            driver.quit()
            exit(1)

        resultados = raspar_produtos(driver, LOJA, QUERY, PAGINAS)
        exibir_resultados(resultados)
        salvar_json(resultados, ARQUIVO)

    finally:
        driver.quit()
        print("\n🔒 Navegador fechado.")
