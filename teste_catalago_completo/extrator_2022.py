"""
╔══════════════════════════════════════════════════════════════════════╗
║     Extrator de Peças — Catálogo Giancar 2022 (PDF baseado em imagem)║
║     Usa OCR (Tesseract) para leitura + lógica de parsing por layout  ║
║     Dois layouts detectados automaticamente por página:              ║
║       • Grade (3 colunas): páginas AMPRI, CEC, CF                   ║
║       • Tabela (2 colunas): páginas BPSA                            ║
╚══════════════════════════════════════════════════════════════════════╝

Dependências:
    pip install pdfplumber pytesseract pillow pandas openpyxl
    + Tesseract OCR instalado no sistema

Uso:
    python extrator_2022.py
"""

import re
import pdfplumber
import pytesseract
import pandas as pd
import pytesseract

# Caminho correto para o seu computador
pytesseract.pytesseract.tesseract_cmd = r'C:\Users\gakir\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
from PIL import Image, ImageEnhance

# ── Configurações ────────────────────────────────────────────────────
CAMINHO_PDF  = "Catálogo2022cpt_teste.pdf"
SAIDA_XLSX   = "pecas_2022.xlsx"
SAIDA_CSV    = "pecas_2022.csv"

# Resolução de renderização das páginas para OCR.
# 250 DPI é um bom equilíbrio entre qualidade e velocidade.
# Use 300 para mais precisão (mais lento).
RESOLUCAO_GRADE  = 250   # páginas de grade (3 colunas)
RESOLUCAO_TABELA = 300   # páginas de tabela (2 colunas) — texto menor, precisa de mais DPI

# Área de crop para páginas de TABELA (remove faixa lateral rotacionada e rodapé)
# Coordenadas em pontos (pt) na página original 595x842
TABELA_CROP = (0, 95, 558, 778)

# Limiar de confiança mínima do OCR para aceitar uma palavra (0-100)
CONF_MINIMA = 35

# ── Expressões regulares ─────────────────────────────────────────────

# Códigos de cada linha de produto no catálogo
# AMPRI XXXXX   — Caixa de direção
# CEC XXX       — Acionador/Centralizador/etc de freio
# CF XXXX       — Bucha, Bieleta, Batente (Centroflex)
# BPSA XXXXXXX  — Jogo de sapata (Brakeparts)
RE_AMPRI = re.compile(r'\bAMPRI\s+(\d{4,6}[A-Z]?)\b')
RE_CEC   = re.compile(r'\bCEC\s+(\d{2,5}(?:\s+\d{2,5})?(?:\s*[A-Z])?)\b')
RE_CF    = re.compile(r'\bCF\s+(\d{3,5}(?:\s*[A-Z])?)\b')
RE_BPSA  = re.compile(r'\bBPSA\s+(\d{7,10})\b')

# Tipo da peça: "Tipo: Dir. hidráulica c/axial"
RE_TIPO  = re.compile(r'Tipo[:\.]?\s*(.+?)(?:\n|$)', re.IGNORECASE)

# Lixo de rodapé a remover
RE_LIXO  = re.compile(
    r'(Tel\.?:?|WhatsApp|giancar\.com|vendas@|94782|2542-9070'
    r'|DISTRIBUIDORA|LINHA DE|BRAKEPARTS|APLICACAO|CODIGO).*',
    re.IGNORECASE
)

# Cabeçalhos de fabricante nas tabelas (linhas de seção)
RE_FABRICANTE = re.compile(
    r'^(AUDI|FIAT|FORD|GM|CHEVROLET|VOLKSWAGEN|RENAULT|PEUGEOT|CITROEN|'
    r'CITRO[EËÊ]N|HONDA|TOYOTA|HYUNDAI|KIA|NISSAN|MERCEDES|BMW|MITSUBISHI|'
    r'VOLVO|LAND ROVER|JEEP|DODGE|CHRYSLER|SUBARU|SUZUKI|ASIA|DAEWOO|'
    r'CHANGAN|CHERY|EFFA|HAFEI|IVECO|JAC|JINBEI|LADA|LEXUS|MAHINDRA|'
    r'MAZDA|PORSCHE|SEAT|SSANGYONG|TROLLER|TOYOTA|GENERAL MOTORS|'
    r'GM\s*[-–]\s*CHEVROLET|GM-CHEVROLET)\s*$',
    re.IGNORECASE
)


# ── Pré-processamento de imagem ──────────────────────────────────────

def preprocessar(img: Image.Image, contraste: float = 2.0) -> Image.Image:
    """
    Converte para escala de cinza e aumenta o contraste.
    Melhora significativamente a acurácia do Tesseract em imagens
    com texto colorido sobre fundo escuro (como os cabeçalhos verdes).
    """
    return ImageEnhance.Contrast(img.convert('L')).enhance(contraste)


# ── Detecção do tipo de layout ───────────────────────────────────────

def detectar_layout(txt_ocr: str) -> str:
    """
    Identifica o tipo de layout da página a partir do texto OCR.

    Retorna uma string indicando o tipo:
      'bpsa'  → tabela de 2 colunas com códigos BPSA
      'grade' → grade de 3 colunas com cards (AMPRI, CEC ou CF)
      'outra' → página de índice, capa, ou em branco (ignorar)
    """
    if 'BPSA' in txt_ocr:
        return 'bpsa'
    if any(p in txt_ocr for p in ('AMPRI', 'CEC ', 'CF ')):
        return 'grade'
    return 'outra'


# ══════════════════════════════════════════════════════════════════════
# LAYOUT BPSA — Tabela de 2 colunas
# ══════════════════════════════════════════════════════════════════════

def extrair_bpsa(page, num_pagina: int) -> list[dict]:
    """
    Extrai peças de páginas no formato tabela BPSA.

    Estrutura visual:
        ┌─────────────────┬─────────────────────────────────────┐
        │ CÓDIGO          │ APLICAÇÃO                           │
        │ BRAKEPARTS      │                                     │
        ├─────────────────┼─────────────────────────────────────┤
        │ BPSA 0095450    │ Topic 12 lugares 93/97              │
        │ BPSA 0097440    │ Towner /98                          │
        │ ...             │ ...                                 │
        └─────────────────┴─────────────────────────────────────┘

    Estratégia:
      1. Recorta a página removendo a faixa lateral rotacionada e rodapé
      2. OCR com PSM 4 (coluna de texto variada)
      3. Parser linha a linha:
         - Linha com BPSA XXXXXXX → novo registro, extrai código + aplicação
         - Linha sem código → propaga o último código visto (OCR perdeu o código)
         - Linha em caixa alta → é nome do fabricante, atualiza grupo
    """
    # Recorta área útil: remove sidebar rotacionado e rodapé
    cropped = page.crop(TABELA_CROP)
    img = cropped.to_image(resolution=RESOLUCAO_TABELA).original
    txt = pytesseract.image_to_string(
        preprocessar(img, contraste=2.0),
        lang='eng',
        config='--psm 4 --oem 3'
    )

    pecas = []
    fabricante_atual = ''
    ultimo_codigo = ''

    for linha in txt.split('\n'):
        linha = linha.strip()

        # Remove caracteres de borda de tabela que o OCR captura
        linha = linha.lstrip('|[ ').rstrip(']| ')
        linha = linha.strip()

        if not linha:
            continue

        # Remove lixo de rodapé
        if RE_LIXO.search(linha):
            continue

        # Detecta cabeçalho de fabricante (linha em caixa alta, sem código)
        if RE_FABRICANTE.match(linha):
            fabricante_atual = linha.title()  # normaliza para Title Case
            continue

        # Tenta extrair código BPSA da linha
        m = RE_BPSA.search(linha)
        if m:
            ultimo_codigo = f'BPSA {m.group(1)}'
            # Aplicação é tudo após o separador '|' ou após o código
            partes = re.split(r'\|', linha, maxsplit=1)
            aplicacao = partes[1].strip() if len(partes) > 1 else ''

            # Se não tem separador, pega tudo após o código
            if not aplicacao:
                idx = linha.find(m.group(0)) + len(m.group(0))
                aplicacao = linha[idx:].strip()

            if ultimo_codigo and aplicacao:
                pecas.append({
                    'grupo'     : 'JOGO DE SAPATA DE FREIO',
                    'fabricante': fabricante_atual,
                    'codigo'    : ultimo_codigo,
                    'tipo'      : '',
                    'aplicacao' : aplicacao,
                    'pagina'    : num_pagina,
                })
        else:
            # Linha sem código BPSA — OCR perdeu o código nessa linha.
            # Propaga o último código visto SE a linha parece uma aplicação
            # (contém letras e não é só números ou lixo)
            conteudo = linha.lstrip('|[ ').rstrip(']| ').strip()
            if ultimo_codigo and conteudo and len(conteudo) > 3:
                # Verifica se não é um cabeçalho de seção
                if not conteudo.isupper() or '/' in conteudo or conteudo[0].isdigit():
                    pecas.append({
                        'grupo'     : 'JOGO DE SAPATA DE FREIO',
                        'fabricante': fabricante_atual,
                        'codigo'    : ultimo_codigo,
                        'tipo'      : '',
                        'aplicacao' : conteudo,
                        'pagina'    : num_pagina,
                    })

    return pecas


# ══════════════════════════════════════════════════════════════════════
# LAYOUT GRADE — Cards em 3 colunas (AMPRI / CEC / CF)
# ══════════════════════════════════════════════════════════════════════

def agrupar_palavras_por_linha(palavras: list[dict], tolerancia_y: int = 12) -> list[list[dict]]:
    """
    Agrupa palavras em linhas com base na proximidade vertical (Y).

    O OCR retorna cada palavra com sua posição. Palavras com Y próximos
    (diferença < tolerancia_y pixels) pertencem à mesma linha visual.

    Retorna lista de linhas, cada linha é lista de palavras ordenadas por X.
    """
    if not palavras:
        return []

    # Ordena por Y primeiro
    palavras_ord = sorted(palavras, key=lambda w: w['y'])
    linhas = []
    linha_atual = [palavras_ord[0]]

    for w in palavras_ord[1:]:
        # Se a diferença de Y é pequena, é a mesma linha
        if abs(w['y'] - linha_atual[-1]['y']) <= tolerancia_y:
            linha_atual.append(w)
        else:
            # Ordena a linha por X antes de fechar
            linhas.append(sorted(linha_atual, key=lambda w: w['x']))
            linha_atual = [w]

    linhas.append(sorted(linha_atual, key=lambda w: w['x']))
    return linhas


def linha_para_texto(linha: list[dict]) -> str:
    """Junta as palavras de uma linha em uma string com espaços."""
    return ' '.join(w['text'] for w in linha)


def detectar_coluna(x: int, largura_pagina_px: int) -> int:
    """
    Determina em qual das 3 colunas uma palavra está.
    Divide a largura da página em 3 faixas iguais.
    Retorna 0, 1 ou 2.
    """
    faixa = largura_pagina_px / 3
    if x < faixa:
        return 0
    elif x < 2 * faixa:
        return 1
    else:
        return 2


def extrair_grade(page, num_pagina: int, grupo_pagina: str) -> list[dict]:
    """
    Extrai peças de páginas no formato grade com cards em 3 colunas.

    Estrutura visual de cada card:
        ┌──────────────────────────────┐
        │ AMPRI 23009          [card]  │
        │ [foto da peça]               │
        │ Tipo: Dir. manual c/axial    │
        │ Modelo    Ano │Modelo   Ano  │
        │ Elba/Fiorino 80/93│Premio... │
        └──────────────────────────────┘

    Estratégia:
      1. OCR com image_to_data para obter coordenadas X,Y de cada palavra
      2. Agrupa palavras em linhas por proximidade Y
      3. Atribui cada linha a uma das 3 colunas (faixas de X)
      4. Dentro de cada coluna, detecta início de card pelo código (AMPRI/CEC/CF)
      5. Tudo após o código até o próximo código = conteúdo do card
    """
    img = page.to_image(resolution=RESOLUCAO_GRADE).original
    img_proc = preprocessar(img, contraste=2.0)

    # image_to_data retorna bounding boxes de cada palavra
    data = pytesseract.image_to_data(
        img_proc,
        lang='eng',
        config='--psm 6 --oem 3',
        output_type=pytesseract.Output.DICT
    )

    # Filtra palavras com confiança mínima e texto não vazio
    palavras = []
    for i, word in enumerate(data['text']):
        conf = int(data['conf'][i])
        if conf >= CONF_MINIMA and word.strip():
            palavras.append({
                'text': word.strip(),
                'x'   : data['left'][i],
                'y'   : data['top'][i],
                'conf': conf,
            })

    if not palavras:
        return []

    # Dimensão horizontal da imagem renderizada
    largura_px = img_proc.width

    # Agrupa palavras em linhas e detecta a coluna de cada linha
    linhas = agrupar_palavras_por_linha(palavras, tolerancia_y=12)

    # Separa as linhas pelas 3 colunas usando o X médio de cada linha
    colunas = [[], [], []]   # lista de (y_medio, texto_da_linha)
    for linha in linhas:
        x_medio = sum(w['x'] for w in linha) / len(linha)
        col = detectar_coluna(x_medio, largura_px)
        y_medio = sum(w['y'] for w in linha) / len(linha)
        texto = linha_para_texto(linha)
        colunas[col].append((y_medio, texto))

    # Para cada coluna, ordena por Y e extrai os cards
    pecas = []
    for col_linhas in colunas:
        col_linhas.sort(key=lambda t: t[0])  # ordena por posição vertical
        extrair_cards_da_coluna(col_linhas, num_pagina, grupo_pagina, pecas)

    return pecas


def extrair_cards_da_coluna(
    linhas: list[tuple],
    num_pagina: int,
    grupo_pagina: str,
    resultado: list
):
    """
    Recebe as linhas de uma coluna e extrai os cards individualmente.

    Cada card começa com uma linha contendo um código AMPRI/CEC/CF.
    O conteúdo do card (tipo e aplicações) vem nas linhas seguintes,
    até o próximo código.

    Atualiza a lista `resultado` com os dicts extraídos.
    """
    codigo_atual = ''
    tipo_atual   = ''
    linhas_conteudo = []

    def salvar_card():
        """Fecha o card atual e adiciona ao resultado."""
        nonlocal codigo_atual, tipo_atual, linhas_conteudo
        if not codigo_atual:
            return

        # Junta o conteúdo do card em uma string limpa
        conteudo = ' '.join(linhas_conteudo).strip()

        # Remove lixo de rodapé que possa ter entrado
        conteudo = RE_LIXO.sub('', conteudo).strip()

        # Remove palavras de template (cabeçalhos de coluna internos)
        conteudo = re.sub(
            r'\b(Modelo|Ano|Tipo|Posicao|Posicdo|Posicgao|Traseira|Dianteira'
            r'|LD|LE|Dir\.?|manual|axial|hidraulica|automatico)\b',
            '', conteudo, flags=re.IGNORECASE
        )
        conteudo = re.sub(r'\s{2,}', ' ', conteudo).strip()

        resultado.append({
            'grupo'     : grupo_pagina,
            'fabricante': '',   # preenchido em pós-processamento
            'codigo'    : codigo_atual,
            'tipo'      : tipo_atual,
            'aplicacao' : conteudo,
            'pagina'    : num_pagina,
        })

        codigo_atual    = ''
        tipo_atual      = ''
        linhas_conteudo = []

    for _, texto in linhas:
        # Ignora linhas de lixo (rodapé, cabeçalho, logos de fabricante)
        if RE_LIXO.search(texto):
            continue

        # Ignora linhas que são só ruído do OCR (menos de 2 chars)
        if len(texto.strip()) < 2:
            continue

        # Detecta código AMPRI
        m = RE_AMPRI.search(texto)
        if m:
            salvar_card()
            codigo_atual = f'AMPRI {m.group(1)}'
            continue

        # Detecta código CEC (ex: CEC 430, CEC 3025 144)
        m = RE_CEC.search(texto)
        if m:
            salvar_card()
            codigo_atual = f'CEC {m.group(1).strip()}'
            continue

        # Detecta código CF (ex: CF 1615, CF 6100 A)
        m = RE_CF.search(texto)
        if m:
            salvar_card()
            codigo_atual = f'CF {m.group(1).strip()}'
            continue

        # Extrai o Tipo da peça (primeira ocorrência após o código)
        if 'Tipo' in texto and not tipo_atual and codigo_atual:
            m_tipo = RE_TIPO.search(texto)
            if m_tipo:
                tipo_atual = m_tipo.group(1).strip()
            continue

        # Todo o resto que não é código nem tipo é conteúdo (modelo/ano/aplicação)
        if codigo_atual:
            # Filtra linhas que são só cabeçalhos internos de tabela
            if texto.strip() not in ('Modelo', 'Ano', 'Modelo Ano', '|Modelo Ano'):
                linhas_conteudo.append(texto)

    # Salva o último card da coluna
    salvar_card()


# ══════════════════════════════════════════════════════════════════════
# Pipeline principal
# ══════════════════════════════════════════════════════════════════════

def processar_pdf(caminho: str) -> pd.DataFrame:
    """
    Função principal: percorre todas as páginas do PDF,
    detecta o layout de cada uma e chama o extrator adequado.

    Retorna um DataFrame com todas as peças encontradas.
    """
    todas_pecas = []
    grupo_grade = ''    # nome do grupo da seção atual (para páginas de grade)

    with pdfplumber.open(caminho) as pdf:
        total = len(pdf.pages)
        print(f"PDF aberto: {total} páginas")
        print(f"Processando com OCR — isso pode levar alguns minutos...")
        print('─' * 60)

        for num in range(total):
            page = pdf.pages[num]
            num_real = num + 1

            # ── Passo 1: OCR rápido para detectar o layout ──────────
            # Usa resolução menor e PSM 4 só para classificar a página
            img_rapida = page.to_image(resolution=120).original
            txt_rapido = pytesseract.image_to_string(
                preprocessar(img_rapida, contraste=2.0),
                lang='eng',
                config='--psm 4 --oem 3'
            )
            layout = detectar_layout(txt_rapido)

            if layout == 'outra':
                print(f"  Pág. {num_real:>2}  |  ignorada (sem dados de peças)")
                continue

            # ── Passo 2: Detecta o grupo/categoria da página ─────────
            # O cabeçalho da página sempre tem o nome da categoria
            # Ex: "CAIXA DE DIREÇÃO", "JOGO DE SAPATA DE FREIO", "BUCHA"
            m_grupo = re.search(
                r'(CAIXA DE DIRE[CÇ]AO|JOGO DE SAPATA|ACIONADOR DE FREIO'
                r'|ALAVANCA DA SAPATA|ALAVANCA DO FREIO|CENTRALIZADOR'
                r'|PARAFUSO SANGRADOR|PINOS?|REGULADOR DE FREIO'
                r'|REPARO DA? (?:SAPATA|ALAVANCA|FREIO)|SAPATA DE FREIO'
                r'|V[AÁ]LVULA EQUALIZADORA|BUCHA|BIELETA|BORRACHA|CAL[CÇ]O'
                r'|COXIM|BATENTE|ARRUELA)',
                txt_rapido, re.IGNORECASE
            )
            if m_grupo:
                grupo_grade = m_grupo.group(0).title()

            # ── Passo 3: Extração específica por layout ──────────────
            if layout == 'bpsa':
                pecas = extrair_bpsa(page, num_real)
                print(f"  Pág. {num_real:>2}  |  BPSA-tabela          |  {len(pecas):>3} registros")

            else:  # layout == 'grade'
                pecas = extrair_grade(page, num_real, grupo_grade)
                print(f"  Pág. {num_real:>2}  |  Grade ({grupo_grade[:20]:<20})  |  {len(pecas):>3} registros")

            todas_pecas.extend(pecas)

    return pd.DataFrame(todas_pecas, columns=[
        'grupo', 'fabricante', 'codigo', 'tipo', 'aplicacao', 'pagina'
    ])


# ── Limpeza pós-extração ─────────────────────────────────────────────

def limpar(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpeza final do DataFrame:
      - Remove espaços extras
      - Remove linhas sem código válido
      - Remove duplicatas
      - Normaliza espaços múltiplos
    """
    # Limpa espaços em todos os campos texto
    for col in ['grupo', 'fabricante', 'codigo', 'tipo', 'aplicacao']:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace('nan', '')
        # Normaliza múltiplos espaços internos
        df[col] = df[col].str.replace(r'\s{2,}', ' ', regex=True)

    # Remove linhas onde código está vazio
    df = df[df['codigo'].str.len() > 0]

    # Remove linhas onde aplicação está vazia (sem dados úteis)
    df = df[df['aplicacao'].str.len() > 2]

    # Remove lixo residual do campo aplicação
    df['aplicacao'] = df['aplicacao'].str.replace(
        RE_LIXO, '', regex=True
    ).str.strip()

    # Remove duplicatas exatas
    df = df.drop_duplicates(
        subset=['codigo', 'aplicacao']
    ).reset_index(drop=True)

    return df


# ── Execução ─────────────────────────────────────────────────────────

if __name__ == '__main__':
    df = processar_pdf(CAMINHO_PDF)
    df = limpar(df)

    df.to_excel(SAIDA_XLSX, index=False)
    df.to_csv(SAIDA_CSV, index=False, encoding='utf-8-sig')

    print('─' * 60)
    print(f"✅ Total extraído   : {len(df)} registros")
    print(f"📂 Grupos únicos   : {df['grupo'].nunique()}")
    print(f"🔑 Códigos únicos  : {df['codigo'].nunique()}")
    print(f"📄 Salvo em        : {SAIDA_XLSX}  e  {SAIDA_CSV}")
    print()
    print("── Amostra ──")
    print(df.head(20).to_string())
    print()
    print("── Por grupo ──")
    print(df['grupo'].value_counts().to_string())