#!/usr/bin/env python3
"""
🤖 Bot de Busca de Produtos no Mercado Livre
Busca produto de vendedor específico. Se não encontrar, retorna vazio.

Uso:
    python main.py "RTX 4060" 123456
    python main.py "i5 13600K" 789012 --format json
    python main.py "iPhone 15" 345678 --output resultado.csv
"""
import argparse
import json
import csv
import sys
from datetime import datetime
from typing import Dict, List, Any

# Tenta importar módulos
try:
    from api_ml import MercadoLivreAPI, buscar_produto_por_vendedor as api_buscar
    API_DISPONIVEL = True
except ImportError:
    API_DISPONIVEL = False

try:
    from selenium_ml import buscar_produto_ml_selenium
    SELENIUM_DISPONIVEL = True
except ImportError:
    SELENIUM_DISPONIVEL = False

from config import Config


def formatar_saida(produtos: List[Dict], formato: str = "console") -> str:
    """Formata a saída conforme solicitado"""
    if not produtos:
        return "❌ Nenhum produto encontrado deste vendedor."

    if formato == "json":
        return json.dumps(produtos, indent=2, ensure_ascii=False)

    elif formato == "csv":
        output = []
        writer = csv.DictWriter(sys.stdout, fieldnames=[
            "id", "title", "price", "currency", "permalink",
            "seller_id", "seller_nickname", "available_quantity"
        ])
        writer.writeheader()
        for p in produtos:
            writer.writerow(p)
        return ""

    else:  # console
        linhas = []
        for p in produtos:
            preco_fmt = f"R$ {p['price']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            linhas.append(f"""
{'='*60}
🛍️  {p['title']}
💰 Preço: {preco_fmt}
📦 Condição: {p.get('condition', 'N/A')}
📦 Disponível: {p.get('available_quantity', 'N/A')} unidade(s)
🚚 Frete: {p.get('shipping', 'N/A')}
👤 Vendedor: {p.get('seller_nickname', 'N/A')} (ID: {p.get('seller_id', 'N/A')})
🔗 {p['permalink']}
{'='*60}
""")
        return "\n".join(linhas)


def salvar_arquivo(produtos: List[Dict], nome_arquivo: str):
    """Salva resultados em arquivo"""
    _, ext = nome_arquivo.rsplit(".", 1) if "." in nome_arquivo else (nome_arquivo, "json")
    ext = ext.lower()

    if ext == "json":
        with open(nome_arquivo, "w", encoding="utf-8") as f:
            json.dump(produtos, f, indent=2, ensure_ascii=False)
    elif ext == "csv":
        with open(nome_arquivo, "w", encoding="utf-8", newline="") as f:
            if produtos:
                writer = csv.DictWriter(f, fieldnames=produtos[0].keys())
                writer.writeheader()
                writer.writerows(produtos)

    print(f"💾 Resultados salvos em: {nome_arquivo}")


def main():
    parser = argparse.ArgumentParser(
        description="Busca produto no Mercado Livre de vendedor específico",
        epilog="""
Exemplos:
  %(prog)s "RTX 4060" 123456
  %(prog)s "iPhone 15" 456789 --format json --output resultado.json
  %(prog)s "Monitor 27" 111222 --format console
        """
    )
    parser.add_argument("query", help="Termo de busca (ex: 'RTX 4060')")
    parser.add_argument("seller_id", type=int, help="ID do vendedor (fornecedor)")
    parser.add_argument(
        "--format", "-f",
        choices=["console", "json", "csv"],
        default="console",
        help="Formato de saída (padrão: console)"
    )
    parser.add_argument("--output", "-o", help="Arquivo para salvar resultado")
    parser.add_argument("--limit", "-l", type=int, default=10, help="Máximo de resultados")
    parser.add_argument(
        "--method", "-m",
        choices=["auto", "api", "selenium"],
        default="auto",
        help="Método: auto (tenta API primeiro), api ou selenium"
    )
    parser.add_argument("--headless", action="store_true", help="Selenium: executar sem janela")

    args = parser.parse_args()

    print(f"🔍 Buscando: '{args.query}' do vendedor {args.seller_id}")
    print(f"⚙️  Método: {args.method} | Formato: {args.format}")

    produtos: List[Dict[str, Any]] = []

    # === TENTATIVA 1: API OFICIAL ===
    if args.method in ("auto", "api") and API_DISPONIVEL:
        if not Config.validate():
            print("⚠️  Credenciais da API não configuradas. Preliminar.")
        else:
            try:
                print("🔑 Tentando API oficial do Mercado Livre...")
                # NOTA: Requer token válido
                # Para simplificar, avisamos que precisa configurar
                print("   ⚠️  API exige token OAuth. Configure no .env")
                print("   Alternativa: use --method selenium")
            except Exception as e:
                print(f"   ❌ Erro na API: {e}")

    # === TENTATIVA 2: SELENIUM ===
    if (args.method in ("auto", "selenium") and (not produtos or args.method == "selenium")):
        if not SELENIUM_DISPONIVEL:
            print("❌ Selenium não disponível. Instale: pip install selenium webdriver-manager")
            sys.exit(1)

        print("🤖 Usando Selenium (automação de navegador)...")
        print("   ⚠️  Em caso de Cloudflare/CAPTCHA, o navegador abrirá para resolver manualmente")
        print("   💡 Use --headless para executar em segundo plano")

        resultados = buscar_produto_ml_selenium(
            query=args.query,
            seller_id=args.seller_id,  # Filtro pós-coleta
            max_results=args.limit,
            headless=args.headless
        )

        # Filtra apenas do vendedor especificado se não veio filtrado
        if args.seller_id and resultados:
            resultados = [r for r in resultados if str(r.get("seller_id")) == str(args.seller_id)]

        produtos = resultados

    # === SAÍDA ===
    if not produtos:
        print("\n❌ Nenhum produto encontrado para o fornecedor especificado.")
        print("   Possíveis causas:")
        print("   • Produto não disponível")
        print("   • Vendedor não tem este item")
        print("   • Bloqueio (Cloudflare/CAPTCHA)")
        print("   • Estrutura da página mudou (necessita atualizar seletores)")
        sys.exit(1)

    print(f"\n✅ Encontrado(s) {len(produtos)} produto(s):")

    # Imprime
    saida = formatar_saida(produtos, args.format)
    if saida:
        print(saida)

    # Salva se --output especificado
    if args.output:
        salvar_arquivo(produtos, args.output)

    print(f"\n🏁 Busca concluída em {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
