"""
Scraper - Loja Atlanta no Mercado Livre
Usa Playwright para renderizar JS e evitar bloqueio micro-landing.
Paginação via clique no botão "Seguinte" — mantém contexto da loja.

Instalação (uma vez):
    pip install playwright
    python -m playwright install chromium
"""

import json
import time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ─────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────
TERMO_BUSCA   = "valvula-gol"   # slug (hifenizado)
LOJA_SLUG     = "atlanta"
MAX_PAGINAS   = 10
ARQUIVO_SAIDA = "resultados_gol_1.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Seletor de card (único — só o que funciona para a loja Atlanta)
CARD_SELETOR = "li.ui-search-layout__item"

# Seletores de título
TITULO_SELETORES = [
    "h2.poly-box",
    "h2[class*='ui-search-item__title']",
    "span[class*='ui-search-item__title']",
    "h2",
    "a[class*='ui-search-link']",
]

# Seletores do botão próxima página
PROXIMO_SELETORES = [
    "a.andes-pagination__link[title='Seguinte']",
    "li.andes-pagination__button--next a",
    "a[title='Siguiente']",
    "a[aria-label='Seguinte']",
    "nav.ui-search-pagination a[title='Seguinte']",
]

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def esperar_cards(page, timeout_ms=15000) -> bool:
    try:
        page.wait_for_selector(CARD_SELETOR, timeout=timeout_ms)
        return True
    except PWTimeout:
        return False


def extrair_texto(el, seletores):
    for sel in seletores:
        found = el.query_selector(sel)
        if found:
            txt = found.inner_text().strip()
            if txt:
                return txt
    return None


def extrair_preco_completo(el):
    fracao = None
    centavos = None

    for sel in [
        "span.poly-price__current .andes-money-amount__fraction",
        "div[class*='poly-price'] .andes-money-amount__fraction",
        "span.price-tag-fraction",
        "span[class*='price-tag-fraction']",
        "span.andes-money-amount__fraction",
    ]:
        found = el.query_selector(sel)
        if found:
            fracao = found.inner_text().strip().replace("\xa0", "").replace(".", "")
            break

    if not fracao:
        return None

    for sel in [
        "span.poly-price__current .andes-money-amount__cents",
        "span.price-tag-cents",
        "span[class*='price-tag-cents']",
        "span.andes-money-amount__cents",
    ]:
        found = el.query_selector(sel)
        if found:
            centavos = found.inner_text().strip()
            break

    return f"R$ {fracao},{centavos}" if centavos else f"R$ {fracao},00"


def extrair_cards(page):
    cards = page.locator(CARD_SELETOR).element_handles()
    print(f"  ✅ {len(cards)} card(s) encontrado(s)")

    produtos = []
    for card in cards:
        titulo  = extrair_texto(card, TITULO_SELETORES) or "Sem título"
        preco   = extrair_preco_completo(card)
        link_el = card.query_selector("a[href]")
        link    = link_el.get_attribute("href") if link_el else None

        if link and "?" in link:
            link = link.split("?")[0]

        produtos.append({
            "titulo": titulo,
            "preco":  preco or "Sem preço",
            "link":   link,
        })

    return produtos


def ir_para_proxima_pagina(page) -> bool:
    """Clica em 'Seguinte' se existir. Retorna True se navegou com sucesso."""
    for sel in PROXIMO_SELETORES:
        btn = page.query_selector(sel)
        if btn:
            btn.click()
            page.wait_for_load_state("domcontentloaded")
            return esperar_cards(page, timeout_ms=15000)
    return False


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    url_inicial = (
        f"https://lista.mercadolivre.com.br/loja/{LOJA_SLUG}"
        f"/{TERMO_BUSCA}_NoIndex_True"
    )
    todos = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        ctx = browser.new_context(
            user_agent=USER_AGENT,
            locale="pt-BR",
            viewport={"width": 1366, "height": 768},
            extra_http_headers={
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        page = ctx.new_page()

        # ── Página 1 ──
        print(f"\n🌐 Acessando página 1: {url_inicial}")
        page.goto(url_inicial, wait_until="domcontentloaded", timeout=30000)

        if not esperar_cards(page):
            print("  ⚠️  Cards não encontrados na página 1. Encerrando.")
            browser.close()
            return

        for pagina in range(1, MAX_PAGINAS + 1):
            print(f"\n📄 Extraindo página {pagina}...")
            produtos = extrair_cards(page)

            if not produtos:
                print("  ℹ️  Página vazia — encerrando.")
                break

            todos.extend(produtos)
            print(f"  📦 {len(produtos)} produto(s) | Total: {len(todos)}")

            if pagina == MAX_PAGINAS:
                break

            time.sleep(2.5)

            print(f"  ➡️  Indo para página {pagina + 1}...")
            if not ir_para_proxima_pagina(page):
                print("  ℹ️  Botão 'Seguinte' não encontrado — fim da listagem.")
                break

        browser.close()

    if todos:
        print(f"\n✅ Total final: {len(todos)} produto(s).")
    else:
        print("\n⚠️  Nenhum produto encontrado.")

    with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)

    print(f"💾 Salvo em '{ARQUIVO_SAIDA}'")


if __name__ == "__main__":
    main()
