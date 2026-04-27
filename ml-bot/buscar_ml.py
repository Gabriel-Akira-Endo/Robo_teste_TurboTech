"""
Busca produtos de um vendedor específico no Mercado Livre.
100% gratuito — sem credenciais, sem OAuth, sem Selenium.
"""
import requests
import json
import sys
from typing import Optional


BASE_URL = "https://api.mercadolibre.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}


# ─────────────────────────────────────────────
# 1. Achar o seller_id pelo nickname do vendedor
# ─────────────────────────────────────────────
def achar_seller_id(nickname: str) -> Optional[dict]:
    """
    Busca o seller_id a partir do nickname (nome do vendedor no ML).
    Exemplo: achar_seller_id("magazineluiza")
    """
    print(f"🔍 Buscando seller_id do vendedor '{nickname}'...")
    resp = requests.get(
        f"{BASE_URL}/sites/MLB/search",
        params={"nickname": nickname, "limit": 1},
        headers=HEADERS
    )
    if resp.status_code != 200:
        print(f"❌ Erro ao buscar vendedor: {resp.status_code}")
        return None

    data = resp.json()
    resultados = data.get("results", [])
    if not resultados:
        print(f"⚠️  Nenhum resultado para o nickname '{nickname}'")
        return None

    seller = resultados[0]["seller"]
    info = {
        "id":       seller["id"],
        "nickname": seller.get("nickname", nickname),
    }
    print(f"✅ Vendedor encontrado: {info['nickname']} (ID: {info['id']})")
    return info


# ─────────────────────────────────────────────
# 2. Buscar produtos de um vendedor pelo seller_id
# ─────────────────────────────────────────────
def buscar_produtos(seller_id: int, query: str = "", max_results: int = 10) -> list:
    """
    Busca produtos de um vendedor específico.
    - seller_id: ID numérico do vendedor
    - query: termo de busca (opcional — se vazio, traz todos os produtos)
    - max_results: quantos resultados retornar (máx 50 por chamada)
    """
    print(f"\n📦 Buscando produtos do vendedor {seller_id}" + (f" | termo: '{query}'" if query else "") + "...")

    params = {
        "seller_id": seller_id,
        "limit":     min(max_results, 50),
    }
    if query:
        params["q"] = query

    resp = requests.get(f"{BASE_URL}/sites/MLB/search", params=params, headers=HEADERS)
    if resp.status_code != 200:
        print(f"❌ Erro na busca: {resp.status_code} — {resp.text}")
        return []

    data = resp.json()
    items = data.get("results", [])
    total = data.get("paging", {}).get("total", 0)
    print(f"✅ {len(items)} produtos retornados (total disponível: {total})")

    resultados = []
    for item in items:
        resultados.append({
            "id":        item.get("id"),
            "titulo":    item.get("title"),
            "preco":     item.get("price"),
            "moeda":     item.get("currency_id", "BRL"),
            "estoque":   item.get("available_quantity"),
            "vendas":    item.get("sold_quantity"),
            "condicao":  item.get("condition"),       # "new" ou "used"
            "frete":     item.get("shipping", {}).get("free_shipping"),
            "link":      item.get("permalink"),
            "thumbnail": item.get("thumbnail"),
        })

    return resultados


# ─────────────────────────────────────────────
# 3. Exibir resultados no console
# ─────────────────────────────────────────────
def exibir_resultados(resultados: list):
    if not resultados:
        print("Nenhum produto encontrado.")
        return

    print(f"\n{'='*60}")
    for i, r in enumerate(resultados, 1):
        frete = "🚚 Frete grátis" if r["frete"] else "📦 Frete a cobrar"
        cond  = "Novo" if r["condicao"] == "new" else "Usado"
        preco = f"R$ {r['preco']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if r["preco"] else "N/A"

        print(f"\n[{i}] {r['titulo']}")
        print(f"     💰 {preco}  |  {frete}  |  {cond}")
        print(f"     📊 Estoque: {r['estoque']}  |  Vendas: {r['vendas']}")
        print(f"     🔗 {r['link']}")
    print(f"\n{'='*60}")


# ─────────────────────────────────────────────
# 4. Salvar em JSON
# ─────────────────────────────────────────────
def salvar_json(resultados: list, arquivo: str = "resultados.json"):
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    print(f"💾 Resultados salvos em '{arquivo}'")


# ─────────────────────────────────────────────
# MAIN — edite aqui para usar
# ─────────────────────────────────────────────
if __name__ == "__main__":

    # ── OPÇÃO A: você já sabe o seller_id ──
    # seller_id = 179571326
    # query     = "notebook"

    # ── OPÇÃO B: você só sabe o nickname ──
    # vendedor = achar_seller_id("magazineluiza")
    # if not vendedor:
    #     sys.exit(1)
    # seller_id = vendedor["id"]
    # query     = "notebook"

    # ── Exemplo rodando direto ──
    # Descubra o seller_id do vendedor que quiser:
    nickname  = "atlanta"           # ← troque pelo nickname do vendedor
    query     = "vávula sandero"         # ← troque pelo produto que quer buscar
    max_items = 10                       # ← quantos produtos quer ver

    vendedor = achar_seller_id(nickname)
    if not vendedor:
        sys.exit(1)

    resultados = buscar_produtos(
        seller_id=vendedor["id"],
        query=query,
        max_results=max_items
    )

    exibir_resultados(resultados)
    salvar_json(resultados)
