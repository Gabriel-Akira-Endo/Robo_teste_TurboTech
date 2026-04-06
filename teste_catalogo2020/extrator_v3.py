"""
╔══════════════════════════════════════════════════════════════════╗
║         Extrator de Peças — Catálogo Giancar 2020 (v3)          ║
║  Abordagem: pdfplumber + agrupamento por bounding boxes reais    ║
║  100% local, sem API externa, sem Poppler                        ║
╚══════════════════════════════════════════════════════════════════╝

Correções aplicadas na v3:
  1. Descrição não é mais separada das aplicações no parser
     → tudo vai para um campo único "desc_e_aplicacoes"
     → evita o corte na primeira palavra minúscula
  2. Limpeza de telefone, WhatsApp e URL no final das strings
  3. Detecção de grupo melhorada: lê também a palavra rotacionada
     na lateral da página (texto vertical "ALAVANCA")
  4. Regex de referência OEM ampliada para aceitar prefixos
     alfanuméricos Ford/GM (ex: BD1M, 96FB, CN15...)

Instalação:
    pip install pdfplumber pandas openpyxl
"""

import re
import pdfplumber
import pandas as pd

# ── Configurações ────────────────────────────────────────────────
CAMINHO_PDF   = "catalogo2020_giancar_compressed.pdf"
SAIDA_XLSX    = "pecas_giancar_v3.xlsx"
SAIDA_CSV     = "pecas_giancar_v3.csv"
PAGINA_INICIO = 4       # 0-based: pula capa e índice (páginas 1-4)

# Posições X reais de cada coluna, detectadas com extract_words().
# O catálogo tem 6 colunas de peças por página, largura ~595pt.
# Cada coluna começa aproximadamente em: 52, 136, 219, 302, 385, 468
COLUNAS_X  = [52, 136, 219, 302, 385, 468]
TOLERANCIA = 50     # raio de captura em torno do X central da coluna

# Gap vertical entre palavras para considerar um novo bloco.
# Se duas palavras estão a mais de 8pt de distância (Y), são blocos diferentes.
GAP_BLOCO  = 8

# ── Expressões regulares ─────────────────────────────────────────

# Código Giancar: 4 a 6 dígitos, opcionalmente seguidos de letra (A, B, C...)
# Exemplos válidos: 10923, 10981A, 43240B, 68103
RE_CODIGO = re.compile(r'^\d{4,6}[A-Z]?$')

# Sufixo de código: letra isolada logo após o número (ex: "10981" + "A")
RE_SUFIXO = re.compile(r'^[A-Z]$')

# Referência OEM — dois padrões possíveis:
#   1. Puramente numérica:      "7 647 562"  (tokens: "7", "647", "562")
#   2. Prefixo alfanumérico:    "BD1M 7202 B", "96FB 2780 AC", "CN15 2780"
#      (prefixo de 2-5 letras seguido de dígitos, comum em Ford/GM/VW)
RE_OEM_NUM   = re.compile(r'^\d+$')
RE_OEM_ALFA  = re.compile(r'^[A-Z]{2,5}\d')   # ex: BD1M, 96FB, CN15, AE8Z

# Grupo da página: linha toda em maiúsculas, pelo menos 4 caracteres
# Exemplos: ALAVANCA, BUCHA, PIVÔ, TERMINAL DE DIREÇÃO
RE_GRUPO = re.compile(r'^[A-ZÁÉÍÓÚÃÕÇÂÊÎÔÛ][A-ZÁÉÍÓÚÃÕÇÂÊÎÔÛ\s]{3,}$')

# Lixo a remover do final das aplicações:
# rodapé do catálogo com telefone, WhatsApp, URL e números de contato
RE_LIXO = re.compile(
    r'(Tel\.?:?|WhatsApp|giancar\.com|vendas@|94782[-\d]+|2542[-\d]+|\(\d{2}\)\s*\d)'
    r'.*$',
    re.IGNORECASE
)

# Palavras/tokens a ignorar na detecção do grupo da página
IGNORAR_GRUPOS = {
    'CATÁLOGO', 'SETEMBRO', 'EDIÇÃO', 'ÍNDICE', 'GRUPO', 'PÁGINA',
    'ACNAVALA',  # palavra "ALAVANCA" rotacionada que aparece invertida
    'FORD', 'FIAT', 'GENERAL', 'MOTORS', 'TEL',
}


# ── Funções utilitárias ──────────────────────────────────────────

def get_coluna(x0: float) -> int:
    """
    Retorna o índice da coluna (0-5) para uma palavra com posição horizontal x0.
    Percorre a lista de posições centrais e verifica qual está dentro da tolerância.
    Retorna -1 se a palavra estiver fora de todas as colunas (ex: rodapé, lateral).
    """
    for i, cx in enumerate(COLUNAS_X):
        if abs(x0 - cx) <= TOLERANCIA:
            return i
    return -1


def separar_blocos(words_coluna: list) -> list[str]:
    """
    Recebe as palavras de uma coluna (já filtradas por X) e as agrupa
    em blocos contíguos, usando o gap vertical como separador.

    Lógica:
      - Ordena as palavras de cima para baixo (por 'top')
      - Se o topo da próxima palavra está mais de GAP_BLOCO pontos abaixo
        do fundo da última palavra do bloco atual → inicia novo bloco
      - Ao final, concatena os textos de cada bloco em uma string

    Retorna lista de strings, uma por bloco.
    """
    if not words_coluna:
        return []

    # Ordena por posição vertical (topo da palavra no PDF)
    ordenados = sorted(words_coluna, key=lambda w: w['top'])

    blocos = []
    atual = [ordenados[0]]

    for w in ordenados[1:]:
        # 'bottom' é o Y inferior da última palavra do bloco atual
        gap = w['top'] - atual[-1]['bottom']
        if gap > GAP_BLOCO:
            # Gap grande → fecha o bloco atual e inicia um novo
            blocos.append(atual)
            atual = [w]
        else:
            # Palavras próximas → mesmo bloco
            atual.append(w)

    blocos.append(atual)  # fecha o último bloco

    # Converte cada grupo de words em uma única string
    return [' '.join(w['text'] for w in b).strip() for b in blocos]


def parse_item(blocos: list[str]) -> dict | None:
    """
    Recebe uma lista de blocos de texto que formam uma peça completa
    e extrai os campos: codigo, ref_oem, desc_e_aplicacoes.

    Estratégia v3:
      - NÃO separa descrição de aplicações — ficam juntos em 'desc_e_aplicacoes'
        evitando o corte errado da v2 (que parava na primeira palavra minúscula)
      - Extrai código e ref OEM com precisão
      - Lida com dois formatos de bloco encontrados no catálogo:

        Formato A — campos em blocos separados (mais comum):
          Bloco 0: "10923"                          → só o código
          Bloco 1: "7 647 562"                      → só a ref OEM
          Bloco 2: "Alavanca do garfo de embreagem" → descrição
          Bloco 3: "Palio Palio Weekend Siena"       → aplicações

        Formato B — código + OEM + desc no mesmo bloco (peças sem foto):
          Bloco 0: "10923 7 647 562"                → código + ref OEM juntos
          Bloco 1: "Alavanca do garfo de embreagem" → descrição
          Bloco 2: "Palio Palio Weekend Siena"       → aplicações

        Formato C — tudo em um bloco único:
          Bloco 0: "10081 A 5 947 511 Alavanca do trambulador ..."
    """
    if not blocos:
        return None

    # Expande todos os blocos em uma sequência flat de tokens para
    # percorrer de forma linear com uma máquina de estados simples
    tokens_flat = []
    for b in blocos:
        tokens_flat.extend(b.split())

    if not tokens_flat:
        return None

    # ── Estado 1: Código ────────────────────────────────────────
    if not RE_CODIGO.match(tokens_flat[0]):
        return None  # primeiro token não é código → descarta

    codigo = tokens_flat[0]
    i = 1

    # Sufixo de letra imediatamente após o código (ex: "10981" + "A")
    if i < len(tokens_flat) and RE_SUFIXO.match(tokens_flat[i]):
        codigo += tokens_flat[i]
        i += 1

    # ── Estado 2: Referência OEM ────────────────────────────────
    # Consome tokens numéricos ou alfanuméricos OEM (BD1M, 96FB...)
    # Para quando encontra um token que claramente é texto descritivo
    ref_partes = []
    while i < len(tokens_flat):
        t = tokens_flat[i]
        if RE_OEM_NUM.match(t) or RE_OEM_ALFA.match(t):
            ref_partes.append(t)
            i += 1
        else:
            break  # chegou na descrição

    ref_oem = ' '.join(ref_partes)

    # ── Estado 3: Descrição + Aplicações (juntos) ───────────────
    # Tudo que sobrou após código e OEM vai para desc_e_aplicacoes.
    # Não tentamos separar descrição de aplicações — isso evita o
    # problema principal da v2 onde "do garfo" era cortado para aplicações.
    desc_e_aplic = ' '.join(tokens_flat[i:]).strip()

    # Remove lixo de rodapé (telefone, WhatsApp, URL) se existir
    desc_e_aplic = RE_LIXO.sub('', desc_e_aplic).strip()

    return {
        'codigo'           : codigo,
        'ref_oem'          : ref_oem,
        'desc_e_aplicacoes': desc_e_aplic,
    }


def detectar_grupo(page) -> str:
    """
    Detecta o grupo/categoria da página.

    Estratégia dupla:
      1. Lê as primeiras linhas do texto extraído (cabeçalho da página)
         Exemplo: "ALAVANCA" no topo → grupo = "ALAVANCA"
      2. Verifica palavras rotacionadas (texto vertical na lateral)
         O PDF tem "ALAVANCA" impresso de lado como separador visual;
         o pdfplumber extrai essa palavra com upright=False e direção 'ttb'
         (top-to-bottom), mas ela aparece invertida como "ACNAVALA"
         → revertemos a string para recuperar o nome real do grupo
    """
    # Estratégia 1: texto normal nas primeiras linhas
    texto = page.extract_text() or ''
    for linha in texto.split('\n')[:5]:
        linha = linha.strip()
        if (RE_GRUPO.match(linha)
                and linha.upper() not in IGNORAR_GRUPOS
                and len(linha) > 3):
            return linha

    # Estratégia 2: palavra rotacionada na lateral
    # Palavras com upright=False estão rotacionadas 90° ou 270°
    words = page.extract_words()
    for w in words:
        if not w.get('upright', True):
            # Inverte a string para corrigir a leitura espelhada
            # "ACNAVALA" → "ALAVANCA"
            candidato = w['text'][::-1].strip()
            if (RE_GRUPO.match(candidato)
                    and candidato.upper() not in IGNORAR_GRUPOS
                    and len(candidato) > 3):
                return candidato

    return ''  # não encontrou grupo nesta página


# ── Pipeline principal ───────────────────────────────────────────

def processar_pdf(caminho: str) -> pd.DataFrame:
    """
    Função principal: percorre todas as páginas do PDF a partir de
    PAGINA_INICIO, detecta o grupo, separa as colunas, agrupa em blocos
    e extrai os dados de cada peça.

    Retorna um DataFrame com todas as peças encontradas.
    """
    pecas = []
    grupo_atual = ''

    with pdfplumber.open(caminho) as pdf:
        total = len(pdf.pages)
        print(f"PDF carregado: {total} páginas")
        print(f"Processando da página {PAGINA_INICIO + 1} até {total}...")
        print('─' * 55)

        for num in range(PAGINA_INICIO, total):
            page    = pdf.pages[num]
            num_real = num + 1

            # Tenta detectar o grupo desta página
            grupo = detectar_grupo(page)
            if grupo:
                grupo_atual = grupo  # atualiza e mantém para as próximas páginas

            words = page.extract_words()
            if not words:
                continue  # página sem texto (ex: só imagem) → pula

            # ── Distribuição das palavras nas 6 colunas ──────────
            # Cada palavra é atribuída à coluna cujo X central está mais próximo
            colunas: list[list] = [[] for _ in range(6)]
            for w in words:
                col = get_coluna(w['x0'])
                if col >= 0:
                    colunas[col].append(w)

            achou = 0

            # ── Processa cada coluna individualmente ─────────────
            for col_words in colunas:
                # Separa as palavras da coluna em blocos por gap vertical
                blocos = separar_blocos(col_words)

                i = 0
                while i < len(blocos):
                    b       = blocos[i]
                    tokens  = b.split()

                    # Verifica se este bloco começa com um código Giancar
                    if tokens and RE_CODIGO.match(tokens[0]):

                        # Agrega os blocos seguintes até encontrar outro código
                        # (máximo de 5 blocos por peça: código, OEM, desc, aplic1, aplic2)
                        sub_blocos = [b]
                        j = i + 1
                        while j < len(blocos) and j <= i + 5:
                            prox = blocos[j].split()
                            # Para se o próximo bloco já é outro código Giancar
                            if prox and RE_CODIGO.match(prox[0]):
                                break
                            sub_blocos.append(blocos[j])
                            j += 1

                        # Tenta extrair os dados da peça
                        item = parse_item(sub_blocos)
                        if item:
                            item['grupo']  = grupo_atual
                            item['pagina'] = num_real
                            pecas.append(item)
                            achou += 1

                        i = j  # avança para o próximo código
                    else:
                        i += 1  # bloco sem código → pula

            print(f"  Pág. {num_real:>3}  |  {grupo_atual:<35}  |  {achou:>3} peças")

    # ── Monta o DataFrame final ──────────────────────────────────
    colunas_df = ['grupo', 'codigo', 'ref_oem', 'desc_e_aplicacoes', 'pagina']
    return pd.DataFrame(pecas, columns=colunas_df)


# ── Limpeza pós-extração ─────────────────────────────────────────

def limpar(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica limpezas finais no DataFrame:
      - Remove espaços extras em todos os campos de texto
      - Remove linhas com código inválido (menos de 4 dígitos, ou que
        sobraram de páginas de índice/capa)
      - Remove duplicatas exatas
      - Propaga grupo para frente (forward fill) para cobrir NaN iniciais
      - Reordena as colunas para leitura mais natural
    """
    # Preenche NaN de grupo com o valor anterior (forward fill)
    df['grupo'] = df['grupo'].replace('', pd.NA).ffill()

    # Limpa espaços extras em todos os campos string
    str_cols = ['grupo', 'codigo', 'ref_oem', 'desc_e_aplicacoes']
    for col in str_cols:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace('nan', '')  # substitui string 'nan' por vazio

    # Remove linhas com código claramente inválido
    df = df[df['codigo'].str.match(r'^\d{4,6}[A-Z]?$')]

    # Remove duplicatas exatas (mesma peça extraída duas vezes)
    df = df.drop_duplicates(subset=['codigo', 'ref_oem', 'desc_e_aplicacoes'])

    # Remove lixo de rodapé que possa ter sobrado
    df['desc_e_aplicacoes'] = df['desc_e_aplicacoes'].str.replace(
        RE_LIXO, '', regex=True
    ).str.strip()

    return df.reset_index(drop=True)


# ── Execução ─────────────────────────────────────────────────────

if __name__ == '__main__':
    # 1. Extrai os dados brutos do PDF
    df = processar_pdf(CAMINHO_PDF)

    # 2. Aplica limpeza pós-extração
    df = limpar(df)

    # 3. Salva os resultados
    df.to_excel(SAIDA_XLSX, index=False)
    df.to_csv(SAIDA_CSV, index=False, encoding='utf-8-sig')

    # 4. Relatório final
    print('─' * 55)
    print(f"✅ Total de peças   : {len(df)}")
    print(f"📂 Grupos únicos   : {df['grupo'].nunique()}")
    print(f"🔍 Sem ref_oem     : {(df['ref_oem'] == '').sum()}")
    print(f"📄 Salvo em        : {SAIDA_XLSX}  e  {SAIDA_CSV}")
    print()
    print("── Amostra dos primeiros registros ──")
    print(df.head(20).to_string())
    print()
    print("── Distribuição por grupo ──")
    print(df['grupo'].value_counts().to_string())
