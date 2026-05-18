"""
Extrator de peças — Catálogo Giancar 2020
Abordagem: pdfplumber + agrupamento por bounding boxes reais (100% local, sem API)
"""

import pdfplumber
import pandas as pd
import re

# ── Configurações ────────────────────────────────────────────────────────────
CAMINHO_PDF   = "catalogo2020_giancar_compressed.pdf"
SAIDA_XLSX    = "pecas_giancar_v2.xlsx"
SAIDA_CSV     = "pecas_giancar_v2.csv"
PAGINA_INICIO = 4       # 0-based: pula capa, contracapa e índice

# Posições X reais de cada coluna (detectadas com extract_words)
COLUNAS_X   = [52, 136, 219, 302, 385, 468]
TOLERANCIA  = 50        # meia-largura de cada coluna (~83px / 2)
GAP_BLOCO   = 8         # gap vertical em pts para separar blocos

# ── Expressões regulares ─────────────────────────────────────────────────────
# Código Giancar: 4–6 dígitos com sufixo opcional (A, B, C...)
RE_CODIGO  = re.compile(r'^\d{4,6}([A-Z]?)$')
RE_SO_NUM  = re.compile(r'^\d+$')
RE_GRUPO   = re.compile(r'^[A-ZÁÉÍÓÚÃÕÇÂÊÎÔÛ][A-ZÁÉÍÓÚÃÕÇÂÊÎÔÛ\s]{3,}$')

IGNORAR_GRUPOS = {
    'CATÁLOGO', 'SETEMBRO', 'EDIÇÃO', 'ÍNDICE', 'GRUPO',
    'PÁGINA', 'ACNAVALA', 'ALAVANCA', 'TEL', 'FORD', 'FIAT',
}

# ── Funções utilitárias ──────────────────────────────────────────────────────

def get_coluna(x0: float) -> int:
    for i, cx in enumerate(COLUNAS_X):
        if abs(x0 - cx) <= TOLERANCIA:
            return i
    return -1


def separar_blocos(words_coluna: list) -> list[str]:
    """Separa words de uma coluna em blocos por gap vertical."""
    if not words_coluna:
        return []
    ordenados = sorted(words_coluna, key=lambda w: w['top'])
    blocos, atual = [], [ordenados[0]]
    for w in ordenados[1:]:
        if w['top'] - atual[-1]['bottom'] > GAP_BLOCO:
            blocos.append(atual)
            atual = [w]
        else:
            atual.append(w)
    blocos.append(atual)
    return [' '.join(w['text'] for w in b).strip() for b in blocos]


def parse_item(texto: str) -> dict | None:
    """
    Recebe o texto concatenado de um item (código + desc + aplicações)
    e retorna um dict com os campos separados.

    Padrão esperado:
      <CODIGO> [SUFIXO]  <NUM_OEM ...>  <Descrição Palavras>  <aplicações...>
    """
    tokens = texto.split()
    if not tokens:
        return None

    # 1. Detecta código (token 0 deve bater com RE_CODIGO)
    m = RE_CODIGO.match(tokens[0])
    if not m:
        return None

    codigo = tokens[0]
    i = 1

    # 2. Sufixo logo após o código (ex: "A", "B") — une ao código
    if i < len(tokens) and re.match(r'^[A-Z]$', tokens[i]):
        codigo += tokens[i]
        i += 1

    # 3. Referência OEM: sequência de tokens numéricos
    ref_partes = []
    while i < len(tokens) and RE_SO_NUM.match(tokens[i]):
        ref_partes.append(tokens[i])
        i += 1
    ref_oem = ' '.join(ref_partes)

    # 4. Descrição: tokens que começam com maiúscula e não são só números
    desc_tokens = []
    while i < len(tokens):
        t = tokens[i]
        if t[0].isupper() and not RE_SO_NUM.match(t):
            desc_tokens.append(t)
            i += 1
        else:
            break
    descricao = ' '.join(desc_tokens)

    # 5. Aplicações: o resto
    aplicacoes = ' '.join(tokens[i:])

    return {
        'codigo'   : codigo,
        'ref_oem'  : ref_oem,
        'descricao': descricao,
        'aplicacoes': aplicacoes,
    }


def detectar_grupo(page) -> str:
    """Retorna o grupo da página lendo as primeiras linhas em caixa alta."""
    texto = page.extract_text() or ''
    for linha in texto.split('\n')[:5]:
        linha = linha.strip()
        if RE_GRUPO.match(linha) and linha.upper() not in IGNORAR_GRUPOS:
            return linha
    return ''


# ── Pipeline principal ───────────────────────────────────────────────────────

def processar_pdf(caminho: str) -> pd.DataFrame:
    pecas = []
    grupo_atual = ''

    with pdfplumber.open(caminho) as pdf:
        total = len(pdf.pages)
        print(f"PDF: {total} páginas  |  Iniciando na pág. {PAGINA_INICIO + 1}")
        print('─' * 55)

        for num in range(PAGINA_INICIO, total):
            page = pdf.pages[num]
            num_real = num + 1

            # Atualiza grupo se a página tiver cabeçalho de categoria
            grupo = detectar_grupo(page)
            if grupo:
                grupo_atual = grupo

            words = page.extract_words()
            if not words:
                continue

            # Distribui words pelas 6 colunas
            colunas: list[list] = [[] for _ in range(6)]
            for w in words:
                col = get_coluna(w['x0'])
                if col >= 0:
                    colunas[col].append(w)

            achou = 0
            for col_words in colunas:
                blocos = separar_blocos(col_words)

                i = 0
                while i < len(blocos):
                    b = blocos[i]
                    tokens = b.split()

                    # Bloco inicia com código Giancar?
                    if tokens and RE_CODIGO.match(tokens[0]):
                        # Agrega até 3 blocos seguintes (desc + aplicações)
                        conteudo = b
                        j = i + 1
                        while j < len(blocos) and j <= i + 3:
                            prox_tokens = blocos[j].split()
                            # Para se o próximo já é outro código
                            if prox_tokens and RE_CODIGO.match(prox_tokens[0]):
                                break
                            conteudo += ' ' + blocos[j]
                            j += 1

                        item = parse_item(conteudo)
                        if item:
                            item['grupo']  = grupo_atual
                            item['pagina'] = num_real
                            pecas.append(item)
                            achou += 1
                        i = j
                    else:
                        i += 1

            print(f"  Pág. {num_real:>3}  |  {grupo_atual:<35}  |  {achou:>3} peças")

    cols = ['grupo', 'codigo', 'ref_oem', 'descricao', 'aplicacoes', 'pagina']
    return pd.DataFrame(pecas, columns=cols)


# ── Execução ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    df = processar_pdf(CAMINHO_PDF)

    # Limpeza básica
    df['codigo']    = df['codigo'].str.strip()
    df['ref_oem']   = df['ref_oem'].str.strip()
    df['descricao'] = df['descricao'].str.strip()
    df['aplicacoes']= df['aplicacoes'].str.strip()

    # Remove linhas sem código válido
    df = df[df['codigo'].str.match(r'^\d{4,6}[A-Z]?$')].reset_index(drop=True)

    df.to_excel(SAIDA_XLSX, index=False)
    df.to_csv(SAIDA_CSV, index=False, encoding='utf-8-sig')

    print('─' * 55)
    print(f"✅ Total de peças   : {len(df)}")
    print(f"📂 Grupos únicos   : {df['grupo'].nunique()}")
    print(f"📄 Salvo em        : {SAIDA_XLSX}  e  {SAIDA_CSV}")
    print()
    print(df.head(20).to_string())