"""
Simulador de Financiamento Imobiliário v2.0
Streamlit App — Abas: Premissas | Fluxos | Análise | Export
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import date

from engine import (
    Premissas, Balao, ResultadoCenario,
    simular_cenario, AnaliseInvestimento,
    baloes_fixos, baloes_custom, calcular_pmt_price
)
from indicadores import (
    get_dataframe, resumo_indicadores,
    media_movel, taxa_anual_de_media, acumulado_12m,
    INDICES_DISPONIVEIS
)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Simulador Financiamento Imobiliário",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# CSS customizado
st.markdown("""
<style>
  .main { background: #F4F8FC; }
  .stTabs [data-baseweb="tab-list"] {
    background: #1F4E79; border-radius: 8px 8px 0 0; padding: 0 8px;
  }
  .stTabs [data-baseweb="tab"] {
    color: #BDD7EE; font-weight: 600; font-size: 15px; padding: 10px 24px;
  }
  .stTabs [aria-selected="true"] {
    color: #FFD966 !important; border-bottom: 3px solid #FFD966;
  }
  .metric-card {
    background: white; border-radius: 10px; padding: 16px;
    border-left: 4px solid #2E75B6; margin-bottom: 8px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  }
  .metric-card.verde { border-left-color: #375623; }
  .metric-card.amarelo { border-left-color: #FFD966; }
  .metric-card.vermelho { border-left-color: #C00000; }
  h1 { color: #1F4E79; }
  .stExpander { border: 1px solid #BDD7EE; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

CORES_CENARIOS = ['#1F4E79', '#2E75B6', '#70AD47', '#FFC000']
NOMES_DEFAULT  = ['Base', 'Entrada +500k', 'Prazo 25a', 'SAC']

# ─────────────────────────────────────────────
# FUNÇÕES AUXILIARES
# ─────────────────────────────────────────────
def fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(',','X').replace('.', ',').replace('X','.')

def fmt_pct(v: float) -> str:
    return f"{v:.2f}%"

def fmt_mult(v: float) -> str:
    return f"{v:.2f}x"

def fmt_mes(v: int) -> str:
    anos  = v // 12
    meses = v % 12
    if anos == 0:
        return f"{meses}m"
    if meses == 0:
        return f"{anos}a"
    return f"{anos}a {meses}m"

@st.cache_data
def get_indicadores_df():
    return get_dataframe()

@st.cache_data
def get_resumo_indicadores():
    return resumo_indicadores()


# ─────────────────────────────────────────────
# SIDEBAR — Configuração dos 4 cenários
# ─────────────────────────────────────────────
def painel_premissas():
    """Retorna lista de 4 Premissas configuradas pelo usuário."""
    premissas_lista = []

    for i in range(4):
        cor   = CORES_CENARIOS[i]
        label = f"Cenário {i+1}"

        with st.expander(f"**{label}**", expanded=(i == 0)):
            col1, col2 = st.columns(2)

            with col1:
                nome = st.text_input("Nome", value=NOMES_DEFAULT[i], key=f"nome_{i}")

                st.markdown("**🏠 Imóvel**")
                valor_imovel = st.number_input("Valor do Imóvel (R$)", min_value=500_000.0,
                    max_value=50_000_000.0, value=7_000_000.0, step=100_000.0,
                    format="%.0f", key=f"imovel_{i}")
                entrada = st.number_input("Entrada (R$)", min_value=0.0,
                    max_value=valor_imovel, value=[1_500_000.0,2_000_000.0,2_500_000.0,1_500_000.0][i],
                    step=100_000.0, format="%.0f", key=f"entrada_{i}")
                vf = valor_imovel - entrada
                st.info(f"💰 Financiado: **{fmt_brl(vf)}**")

                st.markdown("**📈 Análise de Investimento**")
                aluguel = st.number_input("Aluguel atual (R$)", min_value=0.0,
                    value=22_000.0, step=500.0, format="%.0f", key=f"aluguel_{i}")
                valz = st.number_input("Valorização imóvel a.a. (%)", min_value=0.0,
                    max_value=30.0, value=5.0, step=0.5, key=f"valz_{i}")
                custo_op = st.number_input("Custo oportunidade a.a. (%)", min_value=0.0,
                    max_value=30.0, value=14.25, step=0.25, key=f"custo_op_{i}")
                vacancia = st.number_input("Vacância + custos (%)", min_value=0.0,
                    max_value=50.0, value=8.0, step=1.0, key=f"vacancia_{i}")
                taxa_desc = st.number_input("Taxa desconto VPL (%)", min_value=1.0,
                    max_value=30.0, value=15.0, step=0.5, key=f"taxa_desc_{i}")

            with col2:
                st.markdown("**💳 Financiamento**")
                sistema = st.selectbox("Sistema", ["PRICE","SAC"], key=f"sistema_{i}")
                pmt_apos = st.selectbox("PMT após balão", ["FIXO","RECALC"],
                    key=f"pmt_apos_{i}",
                    help="FIXO=prazo reduz | RECALC=PMT reduz")

                modo_taxa = st.selectbox("Modo taxa", ["FIXO","COMPOSTA"], key=f"modo_taxa_{i}")

                if modo_taxa == "FIXO":
                    taxa_aa = st.number_input("Taxa a.a. (%)", min_value=1.0, max_value=30.0,
                        value=[11.99,11.49,11.99,10.99][i], step=0.01, key=f"taxa_{i}")
                    indice_base = "IPCA"; janela = 12; spread = 0.0
                else:
                    indice_base = st.selectbox("Índice base", INDICES_DISPONIVEIS, key=f"indice_{i}")
                    janela = st.slider("Janela média (meses)", 3, 60, 12, key=f"janela_{i}")
                    spread = st.number_input("Spread fixo a.a. (%)", min_value=0.0,
                        max_value=15.0, value=0.8, step=0.1, key=f"spread_{i}")
                    taxa_media = taxa_anual_de_media(indice_base, janela)
                    taxa_aa = taxa_media + spread
                    st.info(f"Taxa efetiva: **{taxa_aa:.2f}% a.a.**\n"
                            f"({indice_base} {janela}m: {taxa_media:.2f}% + {spread:.2f}%)")

                prazo = st.number_input("Prazo (meses)", min_value=12, max_value=420,
                    value=[180,240,300,180][i], step=12, key=f"prazo_{i}")

                reajuste_pmt = st.number_input("Reajuste PMT anual (%)", min_value=0.0,
                    max_value=20.0, value=0.0, step=0.5, key=f"reaj_pmt_{i}",
                    help="% de reajuste da parcela a cada 12 meses")

                indexar = st.checkbox("Indexar saldo devedor?", value=False, key=f"idx_{i}")
                indice_saldo = "TR"; spread_saldo = 0.0
                if indexar:
                    indice_saldo = st.selectbox("Índice saldo", INDICES_DISPONIVEIS, key=f"idx_ind_{i}")
                    spread_saldo = st.number_input("Spread saldo a.a. (%)", 0.0, 10.0, 0.0, key=f"spread_saldo_{i}")

                st.markdown("**🎯 Balões**")
                modo_balao = st.selectbox("Modo balão", ["FIXO","CUSTOM"], key=f"modo_balao_{i}")

                if modo_balao == "FIXO":
                    val_balao = st.number_input("Valor (R$)", min_value=0.0,
                        value=[150_000.0,150_000.0,200_000.0,150_000.0][i],
                        step=10_000.0, format="%.0f", key=f"val_balao_{i}")
                    freq_balao = st.number_input("Frequência (meses)", 6, 60, 12, key=f"freq_{i}")
                    prim_balao = st.number_input("1º balão no mês", 6, 120, 12, key=f"prim_{i}")
                    n_baloes   = st.number_input("Nº máx balões", 1, 20, 8, key=f"nbal_{i}")
                    baloes = baloes_fixos(val_balao, int(freq_balao), int(prim_balao), int(n_baloes))
                else:
                    texto = st.text_area("Balões (MÊS/VALOR por linha)",
                        value="12/150000\n24/150000\n36/150000\n48/150000\n60/150000\n72/150000\n84/150000\n96/150000",
                        key=f"custom_{i}", height=120)
                    baloes = baloes_custom(texto.split('\n'))

                if baloes:
                    total_b = sum(b.valor for b in baloes)
                    st.caption(f"📋 {len(baloes)} balões | Total: {fmt_brl(total_b)}")

            p = Premissas(
                nome=nome,
                valor_imovel=valor_imovel,
                entrada=entrada,
                modo_taxa=modo_taxa,
                taxa_nominal_aa=taxa_aa,
                indice_base=indice_base,
                janela_media=int(janela),
                spread_aa=spread,
                prazo_meses=int(prazo),
                sistema=sistema,
                pmt_apos_balao=pmt_apos,
                reajuste_pmt_aa=reajuste_pmt,
                indexar_saldo=indexar,
                indice_saldo=indice_saldo,
                spread_saldo_aa=spread_saldo,
                baloes=baloes,
                aluguel_atual=aluguel,
                valorizacao_imovel_aa=valz,
                custo_oportunidade_aa=custo_op,
                vacancia_custos_pct=vacancia,
                taxa_desconto_vpl=taxa_desc,
            )
            premissas_lista.append(p)

    return premissas_lista


# ─────────────────────────────────────────────
# ABA 1: PREMISSAS
# ─────────────────────────────────────────────
def aba_premissas(resultados):
    st.markdown("### 📋 Comparativo de Premissas")
    cols = st.columns(4)
    for i, (res, col) in enumerate(zip(resultados, cols)):
        p = res.premissas
        with col:
            cor = CORES_CENARIOS[i]
            st.markdown(f"""
            <div class="metric-card">
              <h4 style="color:{cor};margin:0">C{i+1} — {p.nome}</h4>
              <hr style="margin:6px 0;border-color:#eee">
              <b>Imóvel:</b> {fmt_brl(p.valor_imovel)}<br>
              <b>Entrada:</b> {fmt_brl(p.entrada)}<br>
              <b>Financiado:</b> {fmt_brl(p.valor_financiado)}<br>
              <b>Taxa:</b> {fmt_pct(p.taxa_efetiva_aa)} a.a.<br>
              <b>Prazo:</b> {p.prazo_meses}m ({p.prazo_meses//12} anos)<br>
              <b>Sistema:</b> {p.sistema} | {p.pmt_apos_balao}<br>
              <b>PMT inicial:</b> {fmt_brl(res.pmt_inicial)}<br>
              <b>Balões:</b> {len(p.baloes)}x {fmt_brl(p.baloes[0].valor) if p.baloes else '—'}<br>
              <hr style="margin:6px 0;border-color:#eee">
              <b style="color:{cor}">TOTAL PAGO: {fmt_brl(res.total_pago)}</b><br>
              <b>Mult.:</b> {fmt_mult(res.multiplicador)} | <b>Prazo efetivo:</b> {res.prazo_efetivo}m
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📊 Indicadores Econômicos de Referência")
    df_res = get_resumo_indicadores()
    st.dataframe(df_res.style.format({
        'Média 12m (% a.m.)': '{:.4f}%',
        'Taxa anual equiv. (%)': '{:.2f}%',
        'Acum. 12m (%)': '{:.2f}%',
        'Acum. 5 anos (%)': '{:.1f}%',
        'Acum. 10 anos (%)': '{:.1f}%',
    }), use_container_width=True)

    # Gráfico histórico dos índices
    st.markdown("### 📈 Histórico dos Indicadores (2015–2025)")
    df_hist = get_indicadores_df()
    df_hist['data_str'] = df_hist['data'].dt.strftime('%Y-%m')

    indices_sel = st.multiselect(
        "Selecione os índices", INDICES_DISPONIVEIS,
        default=['IPCA','SELIC','IGP-M'],
        key="ind_hist"
    )

    fig = go.Figure()
    for idx in indices_sel:
        fig.add_trace(go.Scatter(
            x=df_hist['data_str'], y=df_hist[idx],
            name=idx, mode='lines', line=dict(width=2),
        ))
    fig.update_layout(
        title="Taxas mensais históricas (%)",
        xaxis_title="Data", yaxis_title="% a.m.",
        legend=dict(orientation='h', y=1.1),
        height=400, template='plotly_white',
        hovermode='x unified',
    )
    st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────
# ABA 2: FLUXOS
# ─────────────────────────────────────────────
def aba_fluxos(resultados):
    st.markdown("### 💳 Fluxos de Caixa")

    # Métricas rápidas
    cols = st.columns(4)
    for i, (res, col) in enumerate(zip(resultados, cols)):
        with col:
            cor = CORES_CENARIOS[i]
            delta_prazo = res.premissas.prazo_meses - res.prazo_efetivo
            st.metric(
                f"C{i+1} — {res.premissas.nome}",
                fmt_brl(res.total_pago),
                delta=f"-{fmt_mes(delta_prazo)} | {fmt_mult(res.multiplicador)}",
                delta_color="normal"
            )

    st.markdown("---")

    # Gráfico de saldo devedor
    fig_saldo = go.Figure()
    for i, res in enumerate(resultados):
        df = res.to_dataframe()
        fig_saldo.add_trace(go.Scatter(
            x=df['Mês'], y=df['Saldo Final'],
            name=f"C{i+1} — {res.premissas.nome}",
            mode='lines', line=dict(color=CORES_CENARIOS[i], width=2.5),
            hovertemplate='Mês %{x}<br>Saldo: R$ %{y:,.2f}<extra></extra>',
        ))
    fig_saldo.update_layout(
        title="📉 Evolução do Saldo Devedor",
        xaxis_title="Meses", yaxis_title="Saldo (R$)",
        yaxis_tickprefix="R$ ", yaxis_tickformat=",.0f",
        legend=dict(orientation='h', y=1.1),
        height=420, template='plotly_white', hovermode='x unified',
    )
    st.plotly_chart(fig_saldo, use_container_width=True)

    # Gráfico composição do total pago
    fig_comp = go.Figure()
    cats = ['Entrada', 'Total PMTs', 'Total Balões', 'Total Juros']
    fns  = [
        lambda r: r.premissas.entrada,
        lambda r: r.total_pmt,
        lambda r: r.total_balao,
        lambda r: r.total_juros,
    ]
    bar_colors = ['#1F4E79','#2E75B6','#FFC000','#C00000']
    for cat, fn, cor in zip(cats, fns, bar_colors):
        fig_comp.add_trace(go.Bar(
            name=cat,
            x=[f"C{i+1} — {r.premissas.nome}" for i, r in enumerate(resultados)],
            y=[fn(r) for r in resultados],
            marker_color=cor,
        ))
    fig_comp.update_layout(
        barmode='stack', title="💰 Composição do Total Pago",
        yaxis_tickprefix="R$ ", yaxis_tickformat=",.0f",
        legend=dict(orientation='h', y=1.1),
        height=420, template='plotly_white',
    )
    st.plotly_chart(fig_comp, use_container_width=True)

    # Tabela de fluxo por cenário
    st.markdown("### 📋 Fluxo Detalhado")
    tab_sel = st.selectbox("Selecione o cenário", [f"C{i+1} — {r.premissas.nome}" for i, r in enumerate(resultados)])
    idx_sel = int(tab_sel[1]) - 1
    res_sel = resultados[idx_sel]
    df_sel  = res_sel.to_dataframe()

    # Formata colunas BRL
    brl_cols = ['Saldo Inicial','Juros','Amortização','PMT','Balão','Correção Saldo','Saldo Final']
    df_fmt = df_sel.copy()
    for c in brl_cols:
        df_fmt[c] = df_sel[c].apply(fmt_brl)

    st.dataframe(
        df_fmt.style.apply(
            lambda row: ['background-color: #FFF2CC' if row['Evento'] else '' for _ in row],
            axis=1
        ),
        use_container_width=True, height=400
    )


# ─────────────────────────────────────────────
# ABA 3: ANÁLISE DE INVESTIMENTO
# ─────────────────────────────────────────────
def aba_analise(resultados):
    st.markdown("### 📊 Análise de Investimento")

    ais = [AnaliseInvestimento(r) for r in resultados]

    # Cards de métricas por cenário
    cols = st.columns(4)
    for i, (ai, res, col) in enumerate(zip(ais, resultados, cols)):
        tir = ai.tir_imovel()
        vpl = ai.vpl_financiamento()
        be  = ai.ponto_equilibrio()
        co  = ai.custo_oportunidade()
        cor = CORES_CENARIOS[i]
        van_cor = "verde" if co['vantagem_imovel'] >= 0 else "vermelho"
        with col:
            st.markdown(f"""
            <div class="metric-card {van_cor}">
              <h4 style="color:{cor};margin:0">C{i+1} — {res.premissas.nome}</h4>
              <hr style="margin:6px 0;border-color:#eee">
              <b>VPL:</b> {fmt_brl(vpl)}<br>
              <b>TIR imóvel:</b> {fmt_pct(tir or 0)} a.a.<br>
              <b>Cap Rate bruto:</b> {fmt_pct(ai.cap_rate())} a.a.<br>
              <b>Yield líquido:</b> {fmt_pct(ai.yield_liquido())} a.a.<br>
              <b>Break-even valz.:</b> {fmt_pct(ai.break_even_valorizacao())} a.a.<br>
              <b>Equilíbrio R×B:</b> {'Mês '+str(be) if be else '>'+str(res.prazo_efetivo)+'m'}<br>
              <hr style="margin:6px 0;border-color:#eee">
              <b>Patrimônio imóvel:</b> {fmt_brl(co['valor_imovel_final'])}<br>
              <b>Patrimônio RF:</b> {fmt_brl(co['patrimonio_renda_fixa'])}<br>
              <b style="color:{'#375623' if co['vantagem_imovel']>=0 else '#C00000'}">
                Vantagem imóvel: {fmt_brl(co['vantagem_imovel'])}
              </b>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # Rent vs Buy
    st.markdown("### 🏠 vs 💸 Rent vs Buy")
    c1, c2 = st.columns([3, 1])
    with c2:
        idx_rvb = st.selectbox("Cenário", list(range(len(resultados))),
            format_func=lambda i: f"C{i+1} — {resultados[i].premissas.nome}",
            key="rvb_sel")

    df_rvb = ais[idx_rvb].fluxo_rent_vs_buy()
    be_mes = ais[idx_rvb].ponto_equilibrio()

    fig_rvb = go.Figure()
    fig_rvb.add_trace(go.Scatter(
        x=df_rvb['Mês'], y=df_rvb['Patrim. Comprador'],
        name='Patrimônio Líquido (Compra)',
        line=dict(color='#1F4E79', width=2.5),
        hovertemplate='Mês %{x}<br>Patrimônio Compra: R$ %{y:,.2f}<extra></extra>',
    ))
    fig_rvb.add_trace(go.Scatter(
        x=df_rvb['Mês'], y=df_rvb['Capital Aluguel'],
        name='Capital Acumulado (Aluguel)',
        line=dict(color='#C00000', width=2.5, dash='dash'),
        hovertemplate='Mês %{x}<br>Capital Aluguel: R$ %{y:,.2f}<extra></extra>',
    ))
    fig_rvb.add_trace(go.Scatter(
        x=df_rvb['Mês'], y=df_rvb['Aluguel'],
        name='Aluguel Mensal',
        line=dict(color='#FFC000', width=1.5, dash='dot'),
        yaxis='y2',
        hovertemplate='Mês %{x}<br>Aluguel: R$ %{y:,.2f}<extra></extra>',
    ))
    fig_rvb.add_trace(go.Scatter(
        x=df_rvb['Mês'], y=df_rvb['PMT + Balão'],
        name='PMT + Balão',
        line=dict(color='#2E75B6', width=1.5, dash='dot'),
        yaxis='y2',
        hovertemplate='Mês %{x}<br>PMT+Balão: R$ %{y:,.2f}<extra></extra>',
    ))

    if be_mes:
        fig_rvb.add_vline(
            x=be_mes, line_dash="dash", line_color="#375623",
            annotation_text=f"⚖️ Equilíbrio Mês {be_mes}",
            annotation_position="top",
        )

    fig_rvb.update_layout(
        title="Rent vs Buy — Evolução Patrimonial",
        xaxis_title="Meses",
        yaxis=dict(title="Patrimônio (R$)", tickprefix="R$ ", tickformat=",.0f"),
        yaxis2=dict(title="Fluxo mensal (R$)", overlaying='y', side='right',
                    tickprefix="R$ ", tickformat=",.0f"),
        legend=dict(orientation='h', y=1.15),
        height=480, template='plotly_white', hovermode='x unified',
    )
    st.plotly_chart(fig_rvb, use_container_width=True)

    # Custo de oportunidade comparativo
    st.markdown("### 💼 Custo de Oportunidade — Imóvel vs Renda Fixa")
    cos = [ai.custo_oportunidade() for ai in ais]

    fig_co = go.Figure()
    nomes = [f"C{i+1} — {r.premissas.nome}" for i, r in enumerate(resultados)]
    fig_co.add_trace(go.Bar(
        name='Patrimônio — Imóvel Final', x=nomes,
        y=[co['valor_imovel_final'] for co in cos],
        marker_color='#1F4E79',
    ))
    fig_co.add_trace(go.Bar(
        name='Patrimônio — Renda Fixa', x=nomes,
        y=[co['patrimonio_renda_fixa'] for co in cos],
        marker_color='#FFC000',
    ))
    fig_co.update_layout(
        barmode='group', title="Imóvel vs Renda Fixa no prazo efetivo",
        yaxis_tickprefix="R$ ", yaxis_tickformat=",.0f",
        legend=dict(orientation='h', y=1.1),
        height=380, template='plotly_white',
    )
    st.plotly_chart(fig_co, use_container_width=True)


# ─────────────────────────────────────────────
# ABA 4: EXPORT
# ─────────────────────────────────────────────
def aba_export(resultados):
    st.markdown("### 📤 Exportar Análise")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### 📄 PDF")
        fmt_pdf = st.radio("Formato", ["Paisagem — 1920×1080 (apresentação)","Retrato — 1080×1920 (relatório)"],
                           key="fmt_pdf")
        fmt_key = "landscape" if "1920×1080" in fmt_pdf else "portrait"

        if st.button("🖨️ Gerar PDF", use_container_width=True, type="primary"):
            with st.spinner("Gerando PDF..."):
                try:
                    from export_pdf import exportar_pdf
                    pdf_bytes = exportar_pdf(resultados, fmt_key)
                    nome_arq = f"simulador_{fmt_key}.pdf"
                    st.download_button(
                        label=f"⬇️ Baixar {nome_arq}",
                        data=pdf_bytes,
                        file_name=nome_arq,
                        mime="application/pdf",
                        use_container_width=True,
                    )
                    st.success("PDF gerado!")
                except Exception as e:
                    st.error(f"Erro ao gerar PDF: {e}")

    with c2:
        st.markdown("#### 📊 Excel (XLSX)")
        st.write("Inclui: Resumo, Fluxos (4 abas), Análise de Investimento, Indicadores históricos")

        if st.button("📊 Gerar XLSX", use_container_width=True, type="primary"):
            with st.spinner("Gerando XLSX..."):
                try:
                    from export_xlsx import exportar_xlsx
                    xlsx_bytes = exportar_xlsx(resultados)
                    st.download_button(
                        label="⬇️ Baixar simulador.xlsx",
                        data=xlsx_bytes,
                        file_name="simulador_financiamento.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                    st.success("XLSX gerado!")
                except Exception as e:
                    st.error(f"Erro ao gerar XLSX: {e}")

    st.markdown("---")
    st.markdown("#### 📋 Preview — Resumo Comparativo")

    rows = []
    for i, res in enumerate(resultados):
        p  = res.premissas
        ai = AnaliseInvestimento(res)
        tir = ai.tir_imovel()
        co  = ai.custo_oportunidade()
        rows.append({
            'Cenário':           f"C{i+1} — {p.nome}",
            'Imóvel':            fmt_brl(p.valor_imovel),
            'Entrada':           fmt_brl(p.entrada),
            'Financiado':        fmt_brl(p.valor_financiado),
            'Taxa Efetiva a.a.': fmt_pct(p.taxa_efetiva_aa),
            'Prazo':             f"{p.prazo_meses}m",
            'Sistema':           p.sistema,
            'PMT Inicial':       fmt_brl(res.pmt_inicial),
            'PMT Final':         fmt_brl(res.pmt_final),
            'Prazo Efetivo':     f"{res.prazo_efetivo}m",
            'Total PMTs':        fmt_brl(res.total_pmt),
            'Total Balões':      fmt_brl(res.total_balao),
            'Total Juros':       fmt_brl(res.total_juros),
            'TOTAL PAGO':        fmt_brl(res.total_pago),
            'Multiplicador':     fmt_mult(res.multiplicador),
            'TIR Imóvel':        fmt_pct(tir or 0),
            'Vantagem Imóvel':   fmt_brl(co['vantagem_imovel']),
        })

    df_preview = pd.DataFrame(rows).T
    df_preview.columns = [f"C{i+1}" for i in range(len(resultados))]
    st.dataframe(df_preview, use_container_width=True)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    st.markdown("""
    <div style="background:#1F4E79;padding:16px 24px;border-radius:10px;margin-bottom:16px">
      <h2 style="color:white;margin:0">🏠 Simulador de Financiamento Imobiliário v2.0</h2>
      <p style="color:#BDD7EE;margin:4px 0 0 0;font-size:14px">
        PRICE/SAC | Balões | Indexação | VPL/TIR | Rent vs Buy | Export PDF + XLSX
      </p>
    </div>
    """, unsafe_allow_html=True)

    # Configuração dos cenários
    with st.expander("⚙️ **CONFIGURAR CENÁRIOS** — clique para expandir / recolher", expanded=True):
        premissas_lista = painel_premissas()

    # Botão principal
    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        calcular = st.button("▶ CALCULAR", type="primary", use_container_width=True)
    with col_info:
        st.caption("Configure os 4 cenários acima e clique em Calcular para gerar os resultados.")

    if calcular or 'resultados' in st.session_state:
        if calcular:
            with st.spinner("Calculando..."):
                resultados = [simular_cenario(p) for p in premissas_lista]
                st.session_state['resultados'] = resultados
        else:
            resultados = st.session_state['resultados']

        # Abas principais
        tab1, tab2, tab3, tab4 = st.tabs([
            "📋 Premissas",
            "💳 Fluxos",
            "📊 Análise",
            "📤 Export",
        ])

        with tab1:
            aba_premissas(resultados)
        with tab2:
            aba_fluxos(resultados)
        with tab3:
            aba_analise(resultados)
        with tab4:
            aba_export(resultados)


if __name__ == "__main__":
    main()
