# 🤖 Bot de Busca — Mercado Livre

Busca produtos de um **vendedor específico** no ML. Se não encontrar, retorna vazio.

---

## 📦 O que faz

```
Entrada:  termo de busca + ID do fornecedor
Saída:    Se encontrou → retorna preço + link
          Se não → (lista vazia)
```

Exemplo:
```bash
python main.py "RTX 4060" 123456
✅ RTX 4060 8GB — R$ 1.299,00
   https://produto.mercadolivre.com.br/...
```

---

## 📁 Estrutura

```
ml-bot/
├── main.py              # Script principal
├── requirements.txt     # Dependências Python
├── config.py            # Configurações
├── api_ml.py            # ✅ API oficial (recomendada)
├── selenium_ml.py       # 🌐 Fallback navegador
├── .env                 # Suas credenciais (crie)
└── resultado.json       # Saída (se usar --output)
```

---

## 🚀 Instalação

### Windows (CMD/PowerShell):

```powershell
cd "C:\Users\gakir\Documents\3 SEM\front\sprint2\ml-bot"

# Cria ambiente virtual (opcional, mas recomendado)
python -m venv venv
venv\Scripts\Activate.ps1

# Instala dependências
pip install -r requirements.txt

# Copia arquivo de configuração
copy .env.example .env
```

### Edite `.env`:

```env
# Para API oficial, obtenha em: https://developers.mercadolibre.com.br/
MERCADOLIVRE_CLIENT_ID=SEU_CLIENT_ID
MERCADOLIVRE_CLIENT_SECRET=SEU_CLIENT_SECRET
```

> **Nota:** A API exige OAuth2 — veja `api_ml.py` comentado. Para uso imediato, use `--method selenium`.

---

## 🎯 Uso

### 1. Busca simples (Selenium)

```bash
python main.py "RTX 4060" 123456
```

### 2. Busca com formato JSON

```bash
python main.py "RTX 4060" 123456 --format json
```

### 3. Salvar resultado

```bash
python main.py "RTX 4060" 123456 --output resultado.json
```

### 4. Usar API oficial (se configurado)

```bash
python main.py "RTX 4060" 123456 --method api --format json
```

### 5. Sem abrir janela do navegador (headless)

```bash
python main.py "RTX 4060" 123456 --method selenium --headless
```

---

## 🔧 Opções

| Flag | Descrição |
|------|-----------|
| `query` | Termo de busca (obrigatório) |
| `seller_id` | ID do fornecedor (obrigatório) |
| `--format` | `console` \| `json` \| `csv` (padrão: console) |
| `--output` | Salva em arquivo (ex: `resultado.json`) |
| `--limit` | Máximo resultados (padrão: 10) |
| `--method` | `auto` \| `api` \| `selenium` |
| `--headless` | Selenium sem janela |

---

## 🎮 Parâmetros do Fornecedor

### Como obter o ID do vendedor?

1. Acesse o perfil do vendedor no ML
2. URL será algo como: `https://www.mercadolivre.com.br/perfil/USUARIO`
3. O ID numérico nao é tão obvio mas pode ser extraido via API ou inspecionando requests

**Forma mais fácil:** Use a API para buscar produtos do vendedor primeiro:
```python
from api_ml import MercadoLivreAPI
api = MercadoLivreAPI(CLIENT_ID, CLIENT_SECRET)
# Encontre o ID através do nickname
```

---

## 📤 Formato JSON de saída

```json
[
  {
    "id": 1,
    "title": "Placa de Video RTX 4060 8GB",
    "price": 1299.00,
    "price_raw": "R$ 1.299,00",
    "permalink": "https://produto.mercadolivre.com.br/...",
    "seller_id": 123456,
    "seller_nickname": "TechStore Oficial",
    "available_quantity": 3,
    "shipping": "full",
    "found_at": "2025-04-08T14:30:00"
  }
]
```

---

## ⚠️ Avisos

| Problema | Solução |
|---|---|
| **Cloudflare CAPTCHA** | Execute sem `--headless` e resolva manualmente |
| **Estrutura da página mudou** | Atualize os XPaths em `selenium_ml.py` |
| **API token expira** | Implemente refresh OAuth (veja docs ML) |
| **Bloqueio por rate-limit** | Adicione `time.sleep()` entre buscas |

---

## 🐛 Debug

```bash
# Com flag --verbose não implementada, use logs
# Salva screenshots automáticos em caso de erro:
# - debug_ml.png: página de busca
# - erro_ml.png: exception
```

---

## 📊 Exemplo de integração

```python
from main import buscar_produto_por_vendedor

# Em outro script:
resultados = [{
    'query': 'RTX 4060',
    'seller_id': 123456,
    'preco_encontrado': None if not resultados else resultados[0]['price']
}]
```

---

## 📚 Documentação

- API ML: https://developers.mercadolibre.com.br/
- Selenium: https://selenium-python.readthedocs.io/
- Dúvidas: consulte os arquivos `*.py` (comentados)

---

> **Lembre-se:** Use para fins educacionais/pessoais. Respeite os termos do serviço.
