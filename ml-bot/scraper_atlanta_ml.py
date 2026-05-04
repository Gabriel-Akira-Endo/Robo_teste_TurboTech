import requests
from bs4 import BeautifulSoup
import json
import time
import re

# ─────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────
TERMO_BUSCA   = "valvula-gol"        # slug do produto (sem espaços, com hífen)
LOJA_SLUG     = "atlanta"            # slug da loja no ML
MAX_PAGINAS   = 10                   # limite de segurança
ARQUIVO_SAIDA = "resultados_gol_1.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ─────────────────────────────────────────────
# FUNÇÕES
# ─────────────────────────────────────────────

def montar_url(pagina: int) -> str:
    """
    URL correta da loja Atlanta no ML.
    Paginação: offset de 48 itens por página (padrão ML).
    """
    if pagina == 1:
        return (
            f"https://lista.mercadolivre.com.br/loja/{LOJA_SLUG}/"
            f"{TERMO_BUSCA}_NoIndex_True"
        )
    offset = (pagina - 1) * 48
    return (
        f"https://lista.mercadolivre.com.br/loja/{LOJA_SLUG}/"
        f"{TERMO_BUSCA}_Desde_{offset}_NoIndex_True"
    )


def extrair_preco(card) -> str | None:
    """Tenta múltiplos seletores de preço (o ML muda com frequência)."""
    seletores = [
        "span.andes-money-amount__fraction",
        "span[class*='price-tag-fraction']",
        "span[class*='amount__fraction']",
    ]
    for sel in seletores:
        el = card.select_one(sel)
        if el:
            return el.get_text(strip=True)
    return None


def extrair_cards(soup: BeautifulSoup) -> list[dict]:
    """
    Tenta vários seletores de card — o ML usa classes diferentes
    dependendo se é loja, busca normal ou vitrine.
    """
    seletores_container = [
        "li.ui-search-layout__item",          # busca padrão
        "div.ui-search-result__wrapper",       # variante antiga
        "li[class*='ui-search-layout__item']", # variante com sufixo
        "div.andes-card",                      # vitrine de loja
        "div[class*='poly-card']",             # layout novo (2024+)
    ]

    cards = []
    for sel in seletores_container:
        cards = soup.select(sel)
        if cards:
            print(f"  ✅ Seletor usado: {sel!r}  →  {len(cards)} card(s)")
            break

    if not cards:
        # Debug: imprime as primeiras classes encontradas para diagnóstico
        primeiras = [
            tag.get("class", [])
            for tag in soup.find_all(True, limit=60)
            if tag.get("class")
        ]
        classes_unicas = list({" ".join(c) for c in primeiras})[:15]
        print("  ⚠️  Nenhum card encontrado. Classes disponíveis no HTML:")
        for c in classes_unicas:
            print(f"       {c}")
        return []

    produtos = []
    for card in cards:
        # Título
        titulo_el = (
            card.select_one("h2.poly-box")
            or card.select_one("h2[class*='ui-search-item__title']")
            or card.select_one("a[class*='ui-search-link']")
            or card.select_one("h2")
            or card.select_one("a")
        )
        titulo = titulo_el.get_text(strip=True) if titulo_el else "Sem título"

        # Link
        link_el = card.select_one("a[href]")
        link = link_el["href"] if link_el else None

        # Preço
        preco = extrair_preco(card)

        # Seller (útil quando a URL não filtra por loja corretamente)
        seller_el = card.select_one("span[class*='seller']") or card.select_one("p[class*='seller']")
        seller = seller_el.get_text(strip=True) if seller_el else None

        produtos.append({
            "titulo": titulo,
            "preco": preco,
            "seller": seller,
            "link": link,
        })

    return produtos


def scrape() -> list[dict]:
    todos = []

    for pagina in range(1, MAX_PAGINAS + 1):
        url = montar_url(pagina)
        print(f"\n🌐 Acessando página {pagina}: {url}")

        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  ❌ Erro de requisição: {e}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")

        # Verifica se é página "sem resultados"
        sem_resultado = soup.select_one(
            "div.ui-search-rescue, "
            "div[class*='empty-state'], "
            "h2.ui-search-rescue__title"
        )
        if sem_resultado:
            print(f"  ℹ️  Página {pagina} sem resultados — encerrando.")
            break

        produtos = extrair_cards(soup)
        if not produtos:
            print(f"  ⚠️  Página {pagina} retornou 0 produtos — encerrando.")
            break

        print(f"  📦 {len(produtos)} produto(s) encontrado(s) na página {pagina}.")
        todos.extend(produtos)

        # Pausa educada para não bater rate-limit
        time.sleep(2)

    return todos


# ─────────────────────────────────────────────
# EXECUÇÃO
# ─────────────────────────────────────────────
if __name__ == "__main__":
    resultados = scrape()

    if resultados:
        print(f"\n✅ Total geral: {len(resultados)} produto(s).")
    else:
        print("\n⚠️  Nenhum produto encontrado.")

    with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    print(f"💾 Salvo em '{ARQUIVO_SAIDA}'")
