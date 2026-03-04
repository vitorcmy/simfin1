"""
Exportação para PDF — Simulador de Financiamento Imobiliário
Suporta: landscape 1920x1080 e portrait 1080x1920 (em pontos: 1pt = 1/72 pol)
"""

import io
from typing import List
from reportlab.lib import colors

from reportlab.lib.pagesizes import landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable, KeepTogether, PageBreak
)
from reportlab.lib.colors import HexColor
from engine import ResultadoCenario, AnaliseInvestimento

# Paleta
C_AZUL    = HexColor('#1F4E79')
C_AZUL_M  = HexColor('#2E75B6')
C_AZUL_CL = HexColor('#BDD7EE')
C_VERDE   = HexColor('#375623')
C_VERDE_CL= HexColor('#E2EFDA')
C_AMARELO = HexColor('#FFD966')
C_CINZA   = HexColor('#D6DCE4')
C_LARANJA = HexColor('#833C00')
C_BRANCO  = colors.white
C_PRETO   = colors.black
C_CINZA_CL= HexColor('#F2F2F2')

def brl(v):
    if not isinstance(v, (int, float)):
        return str(v)
    return f"R$ {v:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def pct(v):
    return f"{v:.2f}%"

def num(v):
    if not isinstance(v, (int, float)):
        return str(v)
    return f"{v:,.0f}".replace(',', '.')

def mult(v):
    return f"{v:.2f}x"


def _page_size(formato: str):
    """
    'landscape' → 1920×1080 px → pontos (1px = 0.75pt)
    'portrait'  → 1080×1920 px → pontos
    """
    w_px, h_px = (1920, 1080) if formato == 'landscape' else (1080, 1920)
    return (w_px * 0.75, h_px * 0.75)


def exportar_pdf(resultados: List[ResultadoCenario], formato: str = 'landscape') -> bytes:
    """
    formato: 'landscape' (1920x1080) ou 'portrait' (1080x1920)
    """
    buf   = io.BytesIO()
    W, H  = _page_size(formato)
    margin = 36  # 0.5 polegada

    doc = SimpleDocTemplate(
        buf,
        pagesize=(W, H),
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin,
        title="Simulador de Financiamento Imobiliário",
        author="Simulador v2.0",
    )

    styles = getSampleStyleSheet()
    _adicionar_estilos(styles, W)

    story = []

    # Capa
    story += _capa(styles, resultados, formato)
    story.append(PageBreak())

    # Premissas
    story += _secao_premissas(styles, resultados)
    story.append(PageBreak())

    # Resumo comparativo
    story += _secao_resumo(styles, resultados)
    story.append(PageBreak())

    # Análise de Investimento
    story += _secao_analise(styles, resultados)
    story.append(PageBreak())

    # Indicadores
    story += _secao_indicadores(styles)

    doc.build(story)
    return buf.getvalue()


def _adicionar_estilos(styles, page_width):
    base = 10 if page_width > 800 else 8

    styles.add(ParagraphStyle('TituloDoc',
        parent=styles['Title'],
        fontSize=base + 8, textColor=C_BRANCO,
        backColor=C_AZUL, alignment=TA_CENTER,
        spaceBefore=0, spaceAfter=6,
        leading=base + 12,
    ))
    styles.add(ParagraphStyle('SubTitulo',
        parent=styles['Normal'],
        fontSize=base + 2, textColor=C_AZUL,
        alignment=TA_CENTER, spaceAfter=4,
    ))
    styles.add(ParagraphStyle('SecaoHeader',
        parent=styles['Normal'],
        fontSize=base + 1, textColor=C_BRANCO,
        backColor=C_AZUL_M, alignment=TA_LEFT,
        spaceBefore=8, spaceAfter=4,
        leftIndent=6, leading=base + 5,
    ))
    styles.add(ParagraphStyle('Normal9',
        parent=styles['Normal'],
        fontSize=base - 1, textColor=C_PRETO,
    ))
    styles.add(ParagraphStyle('NormalC',
        parent=styles['Normal'],
        fontSize=base - 1, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle('Rodape',
        parent=styles['Normal'],
        fontSize=7, textColor=colors.grey, alignment=TA_CENTER,
    ))


def _ts_base(col_widths, n_header=1):
    """TableStyle base com bordas e headers."""
    return TableStyle([
        ('BACKGROUND',    (0, 0), (-1, n_header-1), C_AZUL_M),
        ('TEXTCOLOR',     (0, 0), (-1, n_header-1), C_BRANCO),
        ('FONTNAME',      (0, 0), (-1, n_header-1), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 8),
        ('ALIGN',         (0, 0), (0, -1), 'LEFT'),
        ('ALIGN',         (1, 0), (-1, -1), 'RIGHT'),
        ('ALIGN',         (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID',          (0, 0), (-1, -1), 0.3, colors.HexColor('#CCCCCC')),
        ('ROWBACKGROUNDS', (0, n_header), (-1, -1), [C_BRANCO, C_CINZA_CL]),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ])


def _capa(styles, resultados, formato):
    items = []
    items.append(Spacer(1, 40))
    items.append(Paragraph("🏠 SIMULADOR DE FINANCIAMENTO IMOBILIÁRIO", styles['TituloDoc']))
    items.append(Spacer(1, 8))
    items.append(Paragraph("Análise Comparativa — 4 Cenários", styles['SubTitulo']))
    items.append(Spacer(1, 4))
    items.append(Paragraph(
        f"Formato: {'Paisagem 1920×1080' if formato=='landscape' else 'Retrato 1080×1920'}  |  "
        f"Cenários: {len(resultados)}",
        styles['SubTitulo']
    ))
    items.append(Spacer(1, 20))
    items.append(HRFlowable(width="100%", thickness=2, color=C_AZUL_M))
    items.append(Spacer(1, 16))

    # Mini tabela de destaque
    hdrs = ['', *[f"C{i+1}\n{r.premissas.nome}" for i, r in enumerate(resultados)]]
    rows = [hdrs]
    linhas_capa = [
        ("Valor do Imóvel",  lambda r: brl(r.premissas.valor_imovel)),
        ("Entrada",          lambda r: brl(r.premissas.entrada)),
        ("Valor Financiado", lambda r: brl(r.premissas.valor_financiado)),
        ("Taxa Efetiva a.a.",lambda r: pct(r.premissas.taxa_efetiva_aa)),
        ("Prazo",            lambda r: f"{r.premissas.prazo_meses}m ({r.premissas.prazo_meses//12} anos)"),
        ("Sistema",          lambda r: r.premissas.sistema),
        ("PMT Inicial",      lambda r: brl(r.pmt_inicial)),
        ("Prazo Efetivo",    lambda r: f"{r.prazo_efetivo} meses"),
        ("TOTAL PAGO",       lambda r: brl(r.total_pago)),
        ("Multiplicador",    lambda r: mult(r.multiplicador)),
    ]
    for label, fn in linhas_capa:
        rows.append([label] + [fn(r) for r in resultados])

    cw = [160] + [130] * len(resultados)
    t = Table(rows, colWidths=cw, repeatRows=1)
    ts = _ts_base(cw)
    # Destaque total pago
    tot_row = len(rows) - 2
    ts.add('BACKGROUND', (0, tot_row), (-1, tot_row), C_AMARELO)
    ts.add('FONTNAME',   (0, tot_row), (-1, tot_row), 'Helvetica-Bold')
    ts.add('TEXTCOLOR',  (0, tot_row), (-1, tot_row), C_PRETO)
    t.setStyle(ts)
    items.append(t)

    items.append(Spacer(1, 20))
    items.append(HRFlowable(width="100%", thickness=1, color=C_CINZA))
    items.append(Spacer(1, 6))
    items.append(Paragraph(
        "Este documento foi gerado automaticamente pelo Simulador de Financiamento Imobiliário v2.0",
        styles['Rodape']
    ))
    return items


def _secao_premissas(styles, resultados):
    items = []
    items.append(Paragraph("PREMISSAS DOS CENÁRIOS", styles['SecaoHeader']))
    items.append(Spacer(1, 6))

    hdrs = ['Variável'] + [f"C{i+1} — {r.premissas.nome}" for i, r in enumerate(resultados)]
    rows = [hdrs]

    grupos = [
        ("── IMÓVEL ──", []),
        ("Valor do Imóvel",        [brl(r.premissas.valor_imovel) for r in resultados]),
        ("Entrada",                [brl(r.premissas.entrada) for r in resultados]),
        ("Valor Financiado",       [brl(r.premissas.valor_financiado) for r in resultados]),
        ("── FINANCIAMENTO ──", []),
        ("Modo Taxa",              [r.premissas.modo_taxa for r in resultados]),
        ("Taxa Efetiva a.a.",      [pct(r.premissas.taxa_efetiva_aa) for r in resultados]),
        ("Taxa Mensal",            [f"{r.premissas.taxa_mensal*100:.4f}%" for r in resultados]),
        ("Prazo (meses)",          [num(r.premissas.prazo_meses) for r in resultados]),
        ("Sistema",                [r.premissas.sistema for r in resultados]),
        ("PMT após balão",         [r.premissas.pmt_apos_balao for r in resultados]),
        ("── BALÕES ──", []),
        ("Nº de Balões",           [num(len(r.premissas.baloes)) for r in resultados]),
        ("Valor 1º Balão",         [brl(r.premissas.baloes[0].valor) if r.premissas.baloes else "—" for r in resultados]),
        ("── ANÁLISE INVEST. ──", []),
        ("Aluguel Atual",          [brl(r.premissas.aluguel_atual) for r in resultados]),
        ("Valoriz. Imóvel a.a.",   [pct(r.premissas.valorizacao_imovel_aa) for r in resultados]),
        ("Custo Oportunidade a.a.",[pct(r.premissas.custo_oportunidade_aa) for r in resultados]),
        ("Taxa Desconto VPL",      [pct(r.premissas.taxa_desconto_vpl) for r in resultados]),
    ]

    header_rows = set()
    for i, (label, vals) in enumerate(grupos):
        if not vals:
            rows.append([label, '', '', '', ''])
            header_rows.add(len(rows) - 1)
        else:
            rows.append([label] + vals)

    cw = [180] + [120] * len(resultados)
    t = Table(rows, colWidths=cw, repeatRows=1)
    ts = _ts_base(cw)
    for hr in header_rows:
        ts.add('BACKGROUND', (0, hr), (-1, hr), C_AZUL)
        ts.add('TEXTCOLOR',  (0, hr), (-1, hr), C_BRANCO)
        ts.add('FONTNAME',   (0, hr), (-1, hr), 'Helvetica-Bold')
        ts.add('SPAN',       (0, hr), (-1, hr))
        ts.add('ALIGN',      (0, hr), (-1, hr), 'LEFT')
    # Label col em azul claro
    for i in range(1, len(rows)):
        if i not in header_rows:
            ts.add('BACKGROUND', (0, i), (0, i), C_AZUL_CL)
            ts.add('FONTNAME',   (0, i), (0, i), 'Helvetica-Bold')
    t.setStyle(ts)
    items.append(t)
    return items


def _secao_resumo(styles, resultados):
    items = []
    items.append(Paragraph("RESUMO COMPARATIVO", styles['SecaoHeader']))
    items.append(Spacer(1, 6))

    hdrs = ['Métrica'] + [f"C{i+1} — {r.premissas.nome}" for i, r in enumerate(resultados)]
    rows = [hdrs]
    header_rows = set()

    grupos = [
        ("RESULTADOS DO FINANCIAMENTO", None),
        ("PMT Inicial",            [brl(r.pmt_inicial) for r in resultados]),
        ("PMT Final",              [brl(r.pmt_final) for r in resultados]),
        ("Prazo Efetivo",          [f"{r.prazo_efetivo} meses" for r in resultados]),
        ("Meses Economizados",     [f"{r.premissas.prazo_meses - r.prazo_efetivo}m" for r in resultados]),
        ("TOTAIS", None),
        ("Total PMTs",             [brl(r.total_pmt) for r in resultados]),
        ("Total Balões",           [brl(r.total_balao) for r in resultados]),
        ("Total Juros",            [brl(r.total_juros) for r in resultados]),
        ("Entrada",                [brl(r.premissas.entrada) for r in resultados]),
        ("TOTAL PAGO",             [brl(r.total_pago) for r in resultados]),
        ("Multiplicador",          [mult(r.multiplicador) for r in resultados]),
        ("ECONOMIA VS CENÁRIO 1", None),
        ("Economia Total",         [brl(resultados[0].total_pago - r.total_pago) for r in resultados]),
        ("Economia Juros",         [brl(resultados[0].total_juros - r.total_juros) for r in resultados]),
        ("Meses a menos",          [f"{resultados[0].prazo_efetivo - r.prazo_efetivo}m" for r in resultados]),
    ]

    total_pago_row = None
    for label, vals in grupos:
        if vals is None:
            rows.append([label, '', '', '', ''])
            header_rows.add(len(rows) - 1)
        else:
            rows.append([label] + vals)
            if label == "TOTAL PAGO":
                total_pago_row = len(rows) - 1

    cw = [180] + [130] * len(resultados)
    t = Table(rows, colWidths=cw, repeatRows=1)
    ts = _ts_base(cw)

    for hr in header_rows:
        ts.add('BACKGROUND', (0, hr), (-1, hr), C_AZUL)
        ts.add('TEXTCOLOR',  (0, hr), (-1, hr), C_BRANCO)
        ts.add('FONTNAME',   (0, hr), (-1, hr), 'Helvetica-Bold')
        ts.add('SPAN',       (0, hr), (-1, hr))
        ts.add('ALIGN',      (0, hr), (-1, hr), 'LEFT')

    if total_pago_row:
        ts.add('BACKGROUND', (0, total_pago_row), (-1, total_pago_row), C_AMARELO)
        ts.add('FONTNAME',   (0, total_pago_row), (-1, total_pago_row), 'Helvetica-Bold')

    # Economia verde
    econ_row = len(rows) - 3
    for cr in range(1, len(resultados)+1):
        ts.add('BACKGROUND', (cr, econ_row),   (-1, econ_row),   C_VERDE_CL)
        ts.add('BACKGROUND', (cr, econ_row+1), (-1, econ_row+1), C_VERDE_CL)
        ts.add('BACKGROUND', (cr, econ_row+2), (-1, econ_row+2), C_VERDE_CL)

    for i in range(1, len(rows)):
        if i not in header_rows:
            ts.add('BACKGROUND', (0, i), (0, i), C_AZUL_CL)
            ts.add('FONTNAME',   (0, i), (0, i), 'Helvetica-Bold')

    t.setStyle(ts)
    items.append(t)
    return items


def _secao_analise(styles, resultados):
    items = []
    items.append(Paragraph("ANÁLISE DE INVESTIMENTO", styles['SecaoHeader']))
    items.append(Spacer(1, 6))

    hdrs = ['Métrica'] + [f"C{i+1} — {r.premissas.nome}" for i, r in enumerate(resultados)]
    rows = [hdrs]
    header_rows = set()

    rows.append(["INDICADORES DE RENTABILIDADE", '', '', '', ''])
    header_rows.add(len(rows) - 1)

    ais = [AnaliseInvestimento(r) for r in resultados]
    metricas = [
        ("VPL do Financiamento",         [brl(ai.vpl_financiamento()) for ai in ais]),
        ("TIR do Imóvel (% a.a.)",        [pct(ai.tir_imovel() or 0) for ai in ais]),
        ("Cap Rate Bruto (% a.a.)",       [pct(ai.cap_rate()) for ai in ais]),
        ("Yield Líquido (% a.a.)",        [pct(ai.yield_liquido()) for ai in ais]),
        ("Break-even Valorização",        [pct(ai.break_even_valorizacao()) for ai in ais]),
        ("Ponto Equilíbrio Rent vs Buy",  [f"Mês {ai.ponto_equilibrio()}" if ai.ponto_equilibrio() else ">" + str(r.prazo_efetivo) + "m" for ai, r in zip(ais, resultados)]),
    ]

    for label, vals in metricas:
        rows.append([label] + vals)

    rows.append(["CUSTO DE OPORTUNIDADE", '', '', '', ''])
    header_rows.add(len(rows) - 1)

    cos = [ai.custo_oportunidade() for ai in ais]
    metricas2 = [
        ("Total Investido",              [brl(co['total_investido_financiamento']) for co in cos]),
        ("Patrimônio — Imóvel Final",    [brl(co['valor_imovel_final']) for co in cos]),
        ("Patrimônio — Renda Fixa",      [brl(co['patrimonio_renda_fixa']) for co in cos]),
        ("Vantagem do Imóvel",           [brl(co['vantagem_imovel']) for co in cos]),
    ]
    for label, vals in metricas2:
        rows.append([label] + vals)

    cw = [200] + [130] * len(resultados)
    t = Table(rows, colWidths=cw, repeatRows=1)
    ts = _ts_base(cw)

    for hr in header_rows:
        ts.add('BACKGROUND', (0, hr), (-1, hr), C_VERDE)
        ts.add('TEXTCOLOR',  (0, hr), (-1, hr), C_BRANCO)
        ts.add('FONTNAME',   (0, hr), (-1, hr), 'Helvetica-Bold')
        ts.add('SPAN',       (0, hr), (-1, hr))
        ts.add('ALIGN',      (0, hr), (-1, hr), 'LEFT')

    for i in range(1, len(rows)):
        if i not in header_rows:
            ts.add('BACKGROUND', (0, i), (0, i), C_AZUL_CL)
            ts.add('FONTNAME',   (0, i), (0, i), 'Helvetica-Bold')

    t.setStyle(ts)
    items.append(t)

    # Nota metodológica
    items.append(Spacer(1, 10))
    items.append(Paragraph(
        "Notas: VPL descontado pela taxa Selic (taxa livre de risco). TIR considera valor de venda projetado no prazo efetivo. "
        "Custo de oportunidade simula reinvestimento de todos os desembolsos em LCI a 95% CDI. "
        "Ponto de equilíbrio rent vs buy considera valorização do imóvel e rendimento do capital não imobilizado.",
        styles['Normal9']
    ))
    return items


def _secao_indicadores(styles):
    from indicadores import resumo_indicadores
    items = []
    items.append(Paragraph("INDICADORES ECONÔMICOS — REFERÊNCIA", styles['SecaoHeader']))
    items.append(Spacer(1, 6))

    df = resumo_indicadores()
    hdrs = list(df.columns)
    rows = [hdrs]
    for _, row in df.iterrows():
        rows.append([
            row['Índice'],
            f"{row['Média 12m (% a.m.)']:.4f}%",
            f"{row['Taxa anual equiv. (%)']:.2f}%",
            f"{row['Acum. 12m (%)']:.2f}%",
            f"{row['Acum. 5 anos (%)']:.1f}%",
            f"{row['Acum. 10 anos (%)']:.1f}%",
        ])

    cw = [80, 110, 110, 90, 100, 100]
    t = Table(rows, colWidths=cw, repeatRows=1)
    ts = _ts_base(cw)
    ts.add('BACKGROUND', (0, 1), (0, -1), C_AZUL_CL)
    ts.add('FONTNAME',   (0, 1), (0, -1), 'Helvetica-Bold')
    t.setStyle(ts)
    items.append(t)

    items.append(Spacer(1, 8))
    items.append(Paragraph(
        "Fontes: IBGE (IPCA), FGV (IGP-M, INCC), SINDUSCON-PR (CUB/PR), Banco Central do Brasil (SELIC, TR, Poupança). "
        "Dados históricos 2015–2025. Valores para referência — verificar fontes primárias para decisões.",
        styles['Normal9']
    ))
    return items
