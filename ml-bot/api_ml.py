"""
Módulo deIntegração com API Oficial do Mercado Livre
Recomendado: mais confiável, sem bloqueios, dados estruturados
"""
import requests
import json
from typing import Optional, Dict, Any, List
from datetime import datetime

from config import Config


class MercadoLivreAPI:
    """Cliente da API oficial do Mercado Livre"""

    TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
    SEARCH_URL = "https://api.mercadolibre.com/sites/MLA/search"
    ITEM_URL = "https://api.mercadolibre.com/items/{item_id}"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expires = None

    def get_access_token(self, force_refresh: bool = False) -> str:
        """
        Obtém token de acesso OAuth2.
        Nota: Implementação simplificada — em produção, persista o token.
        """
        if self.access_token and self.token_expires and not force_refresh:
            if datetime.now().timestamp() < self.token_expires:
                return self.access_token

        print("🔑 Obtendo novo token de acesso...")

        # Para aplicações públicas (client credentials flow limitado)
        # Usuário deve obrer token manualmente ou implementar Authorization Code Flow
        raise NotImplementedError(
            "Para usar a API do ML, você precisa implementar OAuth2.\n"
            "Veja: https://developers.mercadolibre.com.br/pt_br/guides"
        )

    def search_by_seller(
        self,
        query: str,
        seller_id: Optional[int] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Busca produtos por query e opcionalmente filtra por vendedor.

        Args:
            query: Termo de busca (ex: "RTX 4060")
            seller_id: ID do vendedor específico (opcional)
            limit: Máximo de resultados

        Returns:
            Lista de produtos
        """
        params = {
            "q": query,
            "limit": limit,
        }

        if seller_id:
            params["seller_id"] = seller_id

        print(f"🔍 Buscando '{query}' no Mercado Livre...")
        if seller_id:
            print(f"   👤 Filtrando por vendedor ID: {seller_id}")

        try:
            resp = requests.get(
                self.SEARCH_URL,
                params=params,
                timeout=Config.API_TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            print(f"✅ Encontrado(s) {len(results)} resultado(s)")

            return [
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "price": item.get("price"),
                    "currency": item.get("currency_id"),
                    "condition": item.get("condition"),
                    "seller_id": item.get("seller", {}).get("id"),
                    "seller_nickname": item.get("seller", {}).get("nickname"),
                    "permalink": item.get("permalink"),
                    "thumbnail": item.get("thumbnail"),
                    "available_quantity": item.get("available_quantity"),
                    "sold_quantity": item.get("sold_quantity"),
                    "shipping": item.get("shipping", {}).get("logistic_type"),
                    "found_at": datetime.now().isoformat(),
                }
                for item in results
                if seller_id is None or item.get("seller", {}).get("id") == seller_id
            ]

        except requests.RequestException as e:
            print(f"❌ Erro na API: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Código: {e.response.status_code}")
                print(f"   Resposta: {e.response.text[:200]}")
            return []

    def get_item_details(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Obtém detalhes de um item específico"""
        try:
            resp = requests.get(
                self.ITEM_URL.format(item_id=item_id),
                timeout=Config.API_TIMEOUT
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"❌ Erro ao buscar item {item_id}: {e}")
            return None

    @staticmethod
    def format_price(price: float, currency: str = "BRL") -> str:
        """Formata preço para exibição"""
        symbols = {"BRL": "R$", "USD": "$", "ARS": "$"}
        symbol = symbols.get(currency, "")
        return f"{symbol} {price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def buscar_produto_por_vendedor(
    query: str,
    seller_id: int,
    client_id: str,
    client_secret: str
) -> List[Dict]:
    """
    Função principal: busca produto de vendedor específico.

    Returns:
        Lista de produtos encontrados. Vazia se não encontrou.
    """
    api = MercadoLivreAPI(client_id, client_secret)
    return api.search_by_seller(query, seller_id)


# Exemplo de uso direto
if __name__ == "__main__":
    # Configuração (preencher com suas credenciais)
    CLIENT_ID = Config.CLIENT_ID
    CLIENT_SECRET = Config.CLIENT_SECRET

    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ Configure as variáveis MERCADOLIVRE_CLIENT_ID e MERCADOLIVRE_CLIENT_SECRET")
    else:
        # Exemplo: Buscar "RTX 4060" do vendedor 12345
        resultados = buscar_produto_por_vendedor(
            query="RTX 4060",
            seller_id=123456,  # ← Troque pelo ID do fornecedor
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET
        )

        if resultados:
            for prod in resultados:
                print(f"✅ {prod['title']}")
                print(f"   Preço: {MercadoLivreAPI.format_price(prod['price'], prod['currency'])}")
                print(f"   Link: {prod['permalink']}")
        else:
            print("❌ Nenhum produto encontrado deste vendedor.")
