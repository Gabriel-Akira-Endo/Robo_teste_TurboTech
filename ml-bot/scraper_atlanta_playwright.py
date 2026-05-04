"""
Scraper - Loja Atlanta no Mercado Livre
Usa Playwright para renderizar JS e evitar bloqueio micro-landing.

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
ITENS_POR_PAG = 48              # padrão ML
ARQUIVO_SAIDA = "resultados_gol_1.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Seletores de card (tentados em ordem)
CARD_SELETORES = [
    "li.ui-search-layout__item",
    "li[class*='ui-search-layout__item']",
    "div[class*='poly-card']",
    "div.andes-card",
    "div[class*='ui-search-result']",
]

# Seletores de título
TITULO_SELETORES = [
    "h2.poly-box",
    "h2[class*='ui-search-item__title']",
    "span[class*='ui-search-item__title']",
    "h2",
    "a[class*='ui-search-link']",
]

# Seletores de preço — em ordem de prioridade
PRECO_SELETORES = [
    # Novo layout poly (2024+)
    "span.poly-price__current .andes-money-amount__fraction",
    "div[class*='poly-price'] span.andes-money-amount__fraction",
    # Layout padrão de busca
    "span.price-tag-fraction",
    "span[class*='price-tag-fraction']",
    "span.andes-money-amount__fraction",
    # Centavos (separado)
    "span.andes-money-amount__cents",
]

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def montar_url(pagina: int) -> str:
    base = f"https://lista.mercadolivre.com.br/loja/{LOJA_SLUG}/{TERMO_BUSCA}_NoIndex_True"
    if pagina == 1:
        return base
    offset = (pagina - 1) * ITENS_POR_PAG
    return (
        f"https://lista.mercadolivre.com.br/loja/{LOJA_SLUG}/"
        f"{TERMO_BUSCA}_Desde_{offset}_NoIndex_True"
    )


def esperar_conteudo(page, timeout_ms=15000) -> bool:
    """
    Aguarda até que QUALQUER seletor de card apareça.
    Retorna True se encontrou, False se timed-out.
    """
    seletor_combinado = ", ".join(CARD_SELETORES)
    try:
        page.wait_for_selector(seletor_combinado, timeout=timeout_ms)
        return True
    except PWTimeout:
        return False


def extrair_texto(el, seletores: list[str]) -> str | None:
    """Tenta cada seletor em ordem e retorna o primeiro texto encontrado."""
    for sel in seletores:
        found = el.query_selector(sel)
        if found:
            txt = found.inner_text().strip()
            if txt:
                return txt
    return None


def extrair_preco_completo(el) -> str | None:
    """
    Monta o preço completo: fração + centavos (se existir).
    Exemplo: '189' + '90' → 'R$ 189,90'
    """
    fracao = None
    centavos = None

    # Tenta pegar fração principal
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

    # Tenta pegar centavos
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

    if centavos:
        return f"R$ {fracao},{centavos}"
    return f"R$ {fracao},00"


def scrape_pagina(page, pagina: int) -> list[dict]:
    url = montar_url(pagina)
    print(f"\n🌐 Acessando página {pagina}: {url}")

    page.goto(url, wait_until="domcontentloaded", timeout=30000)

    # Aguarda JS renderizar os cards
    encontrou = esperar_conteudo(page, timeout_ms=15000)
    if not encontrou:
        # Diagnóstico
        classes = page.evaluate("""
            () => [...new Set(
                [...document.querySelectorAll('[class]')]
                .flatMap(e => [...e.classList])
            )].slice(0, 30)
        """)
        print(f"  ⚠️  Cards não encontrados. Classes no DOM: {classes}")
        return []

    # Identifica qual seletor funcionou
    card_sel = None
    for sel in CARD_SELETORES:
        if page.locator(sel).count() > 0:
            card_sel = sel
            break

    cards = page.locator(card_sel).all()
    print(f"  ✅ Seletor: {card_sel!r}  →  {len(cards)} card(s)")

    produtos = []
    for card in cards:
        titulo   = extrair_texto(card, TITULO_SELETORES) or "Sem título"
        preco    = extrair_preco_completo(card)
        link_el  = card.query_selector("a[href]")
        link     = link_el.get_attribute("href") if link_el else None

        # Limpa URL (remove tracking)
        if link and "?" in link:
            link = link.split("?")[0]

        produtos.append({
            "titulo": titulo,
            "preco":  preco or "Sem preço",
            "link":   link,
        })

    return produtos


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
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
            # Mascara que é Playwright
            extra_http_headers={
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )

        # Remove propriedade webdriver do JS (anti-detecção)
        ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        page = ctx.new_page()

        for pagina in range(1, MAX_PAGINAS + 1):
            try:
                produtos = scrape_pagina(page, pagina)
            except Exception as e:
                print(f"  ❌ Erro na página {pagina}: {e}")
                break

            if not produtos:
                print(f"  ℹ️  Página {pagina} vazia — encerrando.")
                break

            todos.extend(produtos)
            print(f"  📦 {len(produtos)} produto(s) | Total até agora: {len(todos)}")

            # Pausa entre páginas
            time.sleep(2.5)

        browser.close()

    # ── Salvar resultado ──
    if todos:
        print(f"\n✅ Total final: {len(todos)} produto(s).")
    else:
        print("\n⚠️  Nenhum produto encontrado.")

    with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)

    print(f"💾 Salvo em '{ARQUIVO_SAIDA}'")


if __name__ == "__main__":
    main()
