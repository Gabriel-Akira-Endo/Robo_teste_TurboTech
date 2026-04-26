"""
Módulo de automação com Selenium para Mercado Livre
Fallback para quando API não está disponível.
Cuidado: pode encontrar CAPTCHA/Cloudflare.
"""
import time
import re
from typing import Optional, Dict, Any, List
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from config import Config


def setup_driver(headless: bool = False) -> webdriver.Chrome:
    """Configura o driver do Chrome"""
    options = Options()

    if headless:
        options.add_argument("--headless=new")

    # User agent
    options.add_argument(f"user-agent={Config.USER_AGENT}")

    # Evitar detecção
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # Otimizações
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    driver.set_window_size(1200, 800)
    return driver


def extrair_preco(texto: str) -> Optional[float]:
    """Extrai valor numérico de string de preço (ex: 'R$ 1.299,99')"""
    if not texto:
        return None
    # Remove R$, espaços, converte ponto para decimal
    limpo = re.sub(r'[^\d.,]', '', texto)
    if ',' in limpo and '.' in limpo:
        # Formato brasileiro: 1.999,99
        limpo = limpo.replace('.', '').replace(',', '.')
    elif ',' in limpo:
        # Apenas vírgula como decimal: 999,99
        limpo = limpo.replace(',', '.')
    try:
        return float(limpo)
    except:
        return None


def buscar_produto_ml_selenium(
    query: str,
    seller_id: Optional[int] = None,
    max_results: int = 10,
    headless: bool = False
) -> List[Dict[str, Any]]:
    """
    Busca produtos no Mercado Livre via Selenium.

    Args:
        query: Termo de busca
        seller_id: ID do vendedor (opcional, filtra apenas deste)
        max_results: Máximo de resultados para retornar
        headless: Executa sem janela visual

    Returns:
        Lista de dicionários com produto encontrado
    """
    print(f"🤖 Iniciando busca via Selenium: '{query}'")
    if seller_id:
        print(f"   👤 Filtrando vendedor ID: {seller_id}")

    driver = setup_driver(headless=headless)
    resultados = []

    try:
        # Acessa Mercado Livre
        print("🌐 Acessando mercadolivre.com.br ...")
        driver.get(Config.ML_URL)
        time.sleep(3)

        # Aceita cookies se aparecer
        try:
            cookie_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Aceitar')]"))
            )
            cookie_btn.click()
            time.sleep(1)
        except TimeoutException:
            pass  # Sem cookies

        # Busca
        print(f"🔍 Digitando busca: '{query}'")
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "as-word"))
        )
        search_box.clear()
        search_box.send_keys(query)
        search_box.send_keys(Keys.RETURN)

        time.sleep(4)  # Aguarda carregar resultados

        # Coleta os resultados
        print("📦 Coletando produtos...")

        # Vários seletores possíveis (ML muda DOM ocasionalmente)
        selectors = [
            "//li[contains(@class, 'ui-search-layout__item')]",
            "//div[contains(@class, 'ui-search-result')]",
            "//div[@data-testid='product-card']",
        ]

        items = []
        for selector in selectors:
            try:
                items = driver.find_elements(By.XPATH, selector)
                if items:
                    print(f"   📊 Encontrados {len(items)} itens")
                    break
            except:
                continue

        if not items:
            print("⚠️  Nenhum item encontrado com os seletores conhecidos.")
            # Salva screenshot para debug
            driver.save_screenshot("debug_ml.png")
            print("   Screenshot salvo: debug_ml.png")

        for idx, item in enumerate(items[:max_results]):
            try:
                # Título
                title_elem = item.find_element(
                    By.XPATH, ".//h2"  # Título usualmente em h2
                ) or item.find_element(
                    By.XPATH, ".//span[contains(@class, 'title')]"
                )
                title = title_elem.text.strip()

                # Preço
                price_elem = item.find_element(
                    By.XPATH, ".//span[contains(@class, 'price')]"
                ) or item.find_element(
                    By.XPATH, ".//div[contains(@class, 'price')]"
                )
                price_raw = price_elem.text.strip()
                price = extrair_preco(price_raw)

                # Link
                link_elem = item.find_element(By.XPATH, ".//a")
                link = link_elem.get_attribute("href")

                # Vendedor — precisa clicar no produto para ver
                seller_id_found = None
                seller_name = None

                # Se seller_id foi especificado, verifica se é o fornecedor certo
                # Para isso precisaríamos abrir o produto, o que é lento
                # Alternativa: confiar apenas no filtro da URL (abaixo)

                resultados.append({
                    "id": idx + 1,
                    "title": title,
                    "price": price,
                    "price_raw": price_raw,
                    "link": link,
                    "seller_id": seller_id_found,
                    "seller_name": seller_name,
                    "source": "selenium",
                    "found_at": time.strftime("%Y-%m-%d %H:%M:%S")
                })

            except Exception as e:
                # print(f"   ⚠️  Erro no item {idx}: {e}")
                continue

        print(f"✅ Coletados {len(resultados)} produtos")

    except Exception as e:
        print(f"❌ Erro durante automação: {e}")
        driver.save_screenshot("erro_ml.png")
        print("   Screenshot salvo: erro_ml.png")
    finally:
        driver.quit()
        print("🔒 Navegador fechado.")

    return resultados


def filtrar_por_vendedor_id(
    resultados: List[Dict[str, Any]],
    seller_id: int
) -> List[Dict[str, Any]]:
    """
    Filtra resultados para manter apenas os do vendedor especificado.
    Nota: Requer abrir cada link para verificar o seller_id (lento).
    """
    print(f"🔍 Filtrando por vendedor ID {seller_id}...")
    # Esta função seria mais complexa — pular por enquanto
    return resultados


if __name__ == "__main__":
    # DEBUG
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "RTX 4060"
    seller = int(sys.argv[2]) if len(sys.argv) > 2 else None

    resultados = buscar_produto_ml_selenium(query, seller_id=seller, headless=False)

    for r in resultados:
        print(f"• {r['title']}")
        print(f"  💰 {r['price_raw']}")
        print(f"  🔗 {r['link']}\n")
