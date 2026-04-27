"""
Busca produtos de uma loja específica no Mercado Livre via scraping.
100% gratuito — sem credenciais, sem OAuth, sem Selenium.

Instalar dependências:
    pip install requests beautifulsoup4
"""
import requests
import json
import time
from bs4 import BeautifulSoup
from typing import Optional

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ─────────────────────────────────────────────
# 1. Busca produtos de uma loja pelo slug da URL
# ─────────────────────────────────────────────
def buscar_loja(slug: str, query: str = "", paginas: int = 1) -> list:
    """
    Busca produtos de uma loja específica.
    - slug:    nome da loja na URL  ex: 'atlanta'
    - query:   termo de busca       ex: 'valvula sandero'
    - paginas: quantas páginas quer raspar (cada uma tem ~48 produtos)
    """
    resultados = []

    for pagina in range(paginas):
        offset = pagina * 48
        if query:
            # Busca com filtro de loja + termo
            url = f"https://lista.mercadolivre.com.br/{query.replace(' ', '-')}_Loja_{slug}"
        else:
            # Todos os produtos da loja
            url = f"https://www.mercadolivre.com.br/loja/{slug}/mais-vendidos"

        if offset > 0:
            url += f"_Desde_{offset + 1}"

        print(f"🌐 Acessando página {pagina + 1}: {url}")
        resp = requests.get(url, headers=HEADERS)

        if resp.status_code != 200:
            print(f"❌ Erro HTTP {resp.status_code}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select(".ui-search-layout__item")

        if not cards:
            print(f"⚠️  Nenhum card encontrado na página {pagina + 1}")
            break

        print(f"📦 {len(cards)} produtos encontrados na página {pagina + 1}")

        for card in cards:
            titulo   = _pegar_texto(card, ".poly-component__title")
            preco    = _pegar_preco(card)
            link     = _pegar_link(card)
            vendedor = _pegar_texto(card, ".poly-component__seller")
            frete    = card.select_one(".poly-component__shipping") is not None

            resultados.append({
                "titulo":       titulo,
                "preco":        preco,
                "vendedor":     vendedor,
                "frete_gratis": frete,
                "link":         link,
            })

        time.sleep(1.5)  # respeita o servidor entre páginas

    return resultados


# ─────────────────────────────────────────────
# Helpers de extração
# ─────────────────────────────────────────────
def _pegar_texto(card, seletor: str) -> Optional[str]:
    el = card.select_one(seletor)
    return el.get_text(strip=True) if el else None


def _pegar_link(card) -> Optional[str]:
    el = card.select_one("a.poly-component__title")
    if not el:
        el = card.select_one("a")
    return el["href"] if el and el.get("href") else None


def _pegar_preco(card) -> Optional[float]:
    fracao = card.select_one(".andes-money-amount__fraction")
    cents  = card.select_one(".andes-money-amount__cents")
    if not fracao:
        return None
    try:
        valor = fracao.get_text(strip=True).replace(".", "")
        if cents:
            valor += f".{cents.get_text(strip=True)}"
        return float(valor)
    except:
        return None


# ─────────────────────────────────────────────
# 2. Exibir no console
# ─────────────────────────────────────────────
def exibir_resultados(resultados: list):
    if not resultados:
        print("\n⚠️  Nenhum produto encontrado.")
        return

    print(f"\n{'='*65}")
    for i, r in enumerate(resultados, 1):
        preco = f"R$ {r['preco']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if r["preco"] else "N/A"
        frete = "🚚 Frete grátis" if r["frete_gratis"] else "📦 Sem frete grátis"

        print(f"\n[{i}] {r['titulo']}")
        print(f"     💰 {preco}  |  {frete}")
        if r["vendedor"]:
            print(f"     🏪 {r['vendedor']}")
        print(f"     🔗 {r['link']}")
    print(f"\n{'='*65}")
    print(f"Total: {len(resultados)} produtos")


# ─────────────────────────────────────────────
# 3. Salvar em JSON
# ─────────────────────────────────────────────
def salvar_json(resultados: list, arquivo: str = "resultados_gol.json"):
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Salvo em '{arquivo}'")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":

    LOJA    = "atlanta"          # ← slug da URL: mercadolivre.com.br/loja/atlanta
    QUERY   = "valvula gol"  # ← produto que quer buscar (deixa "" para ver tudo)
    PAGINAS = 1                  # ← aumente para raspar mais páginas (48 produtos cada)

    resultados = buscar_loja(slug=LOJA, query=QUERY, paginas=PAGINAS)
    exibir_resultados(resultados)
    salvar_json(resultados)
