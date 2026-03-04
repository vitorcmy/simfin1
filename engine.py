"""
Motor de cálculos financeiros — Simulador de Financiamento Imobiliário
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional
from indicadores import media_movel, taxa_anual_de_media

# ---------------------------------------------------------------------------
# Estruturas de dados
# ---------------------------------------------------------------------------

@dataclass
class Balao:
    mes: int
    valor: float

@dataclass
class Premissas:
    # Identificação
    nome: str = "Cenário"

    # Imóvel
    valor_imovel: float = 7_000_000.0
    entrada: float = 1_500_000.0

    # Financiamento
    modo_taxa: str = "FIXO"          # FIXO | COMPOSTA
    taxa_nominal_aa: float = 11.99   # usada quando modo=FIXO
    indice_base: str = "IPCA"        # usado quando modo=COMPOSTA
    janela_media: int = 12
    spread_aa: float = 0.8           # spread sobre índice (modo COMPOSTA)
    prazo_meses: int = 180
    sistema: str = "PRICE"           # PRICE | SAC
    pmt_apos_balao: str = "FIXO"     # FIXO | RECALC
    reajuste_pmt_aa: float = 0.0     # % reajuste anual do PMT

    # Indexação do saldo devedor
    indexar_saldo: bool = False
    indice_saldo: str = "TR"
    spread_saldo_aa: float = 0.0

    # Balões
    baloes: List[Balao] = field(default_factory=list)

    # Análise de investimento
    aluguel_atual: float = 22_000.0
    reajuste_aluguel_aa: float = 0.0    # 0 = usa índice IGP-M
    indice_aluguel: str = "IGP-M"
    valorizacao_imovel_aa: float = 5.0  # % a.a.
    taxa_desconto_vpl: float = 15.0     # % a.a. (Selic)
    custo_oportunidade_aa: float = 14.25  # % a.a. (LCI 95% CDI)
    vacancia_custos_pct: float = 8.0    # % sobre aluguel

    @property
    def valor_financiado(self) -> float:
        return self.valor_imovel - self.entrada

    @property
    def taxa_efetiva_aa(self) -> float:
        if self.modo_taxa == "COMPOSTA":
            media_mensal = media_movel(self.indice_base, self.janela_media)
            taxa_aa_indice = (pow(1 + media_mensal / 100, 12) - 1) * 100
            return taxa_aa_indice + self.spread_aa
        return self.taxa_nominal_aa

    @property
    def taxa_mensal(self) -> float:
        return pow(1 + self.taxa_efetiva_aa / 100, 1 / 12) - 1

    @property
    def taxa_saldo_mensal(self) -> float:
        if not self.indexar_saldo:
            return 0.0
        media_mensal = media_movel(self.indice_saldo, 12)
        taxa_aa = (pow(1 + media_mensal / 100, 12) - 1) * 100 + self.spread_saldo_aa
        return pow(1 + taxa_aa / 100, 1 / 12) - 1


@dataclass
class LinhaFluxo:
    mes: int
    saldo_inicial: float
    juros: float
    amortizacao: float
    pmt: float
    balao: float
    correcao_saldo: float
    saldo_final: float
    pmt_novo: Optional[float] = None  # se houve recalculo
    evento: str = ""


@dataclass
class ResultadoCenario:
    premissas: Premissas
    fluxo: List[LinhaFluxo]

    @property
    def prazo_efetivo(self) -> int:
        return len(self.fluxo)

    @property
    def pmt_inicial(self) -> float:
        return self.fluxo[0].pmt if self.fluxo else 0.0

    @property
    def pmt_final(self) -> float:
        return self.fluxo[-1].pmt if self.fluxo else 0.0

    @property
    def total_pmt(self) -> float:
        return sum(r.pmt for r in self.fluxo)

    @property
    def total_juros(self) -> float:
        return sum(r.juros for r in self.fluxo)

    @property
    def total_amortizacao(self) -> float:
        return sum(r.amortizacao for r in self.fluxo)

    @property
    def total_balao(self) -> float:
        return sum(r.balao for r in self.fluxo)

    @property
    def total_correcao(self) -> float:
        return sum(r.correcao_saldo for r in self.fluxo)

    @property
    def total_pago(self) -> float:
        return self.total_pmt + self.total_balao + self.premissas.entrada

    @property
    def multiplicador(self) -> float:
        return self.total_pago / self.premissas.valor_imovel if self.premissas.valor_imovel > 0 else 0.0

    @property
    def cet_anual(self) -> float:
        """Custo Efetivo Total aproximado (sem seguros)."""
        return self.premissas.taxa_efetiva_aa

    def to_dataframe(self) -> pd.DataFrame:
        rows = []
        for r in self.fluxo:
            rows.append({
                'Mês': r.mes,
                'Saldo Inicial': r.saldo_inicial,
                'Juros': r.juros,
                'Amortização': r.amortizacao,
                'PMT': r.pmt,
                'Balão': r.balao,
                'Correção Saldo': r.correcao_saldo,
                'Saldo Final': r.saldo_final,
                'Evento': r.evento,
            })
        return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Funções de cálculo
# ---------------------------------------------------------------------------

def calcular_pmt_price(pv: float, tm: float, n: int) -> float:
    if tm == 0:
        return pv / n
    return pv * tm * pow(1 + tm, n) / (pow(1 + tm, n) - 1)


def simular_cenario(p: Premissas) -> ResultadoCenario:
    tm = p.taxa_mensal
    ts = p.taxa_saldo_mensal
    pv = p.valor_financiado
    n  = p.prazo_meses

    # PMT inicial
    if p.sistema == "PRICE":
        pmt_atual = calcular_pmt_price(pv, tm, n)
    else:  # SAC
        pmt_atual = None  # calculado por mês

    # Mapa de balões por mês
    mapa_baloes = {b.mes: b.valor for b in p.baloes}

    saldo     = pv
    fluxo     = []
    pmt_vigente = pmt_atual

    for mes in range(1, n + 1):
        saldo_ini = saldo

        # Reajuste anual do PMT (meses múltiplos de 12, após o 1º ano)
        if p.reajuste_pmt_aa > 0 and mes > 12 and mes % 12 == 1 and p.sistema == "PRICE":
            pmt_vigente *= (1 + p.reajuste_pmt_aa / 100)

        # Juros e amortização
        juros = saldo * tm

        if p.sistema == "SAC":
            amort = pv / n
            pmt_mes = amort + juros
        else:
            amort = pmt_vigente - juros
            pmt_mes = pmt_vigente

        novo_saldo = saldo - amort

        # Correção do saldo devedor
        correcao = novo_saldo * ts if ts > 0 else 0.0
        novo_saldo += correcao

        # Balão
        balao_mes = 0.0
        evento    = ""
        pmt_novo  = None

        if mes in mapa_baloes and novo_saldo > 0.01:
            bval = mapa_baloes[mes]
            if novo_saldo <= bval:
                balao_mes  = max(novo_saldo, 0.0)
                novo_saldo = 0.0
                evento     = "Balão (quitação)"
            else:
                balao_mes  = bval
                novo_saldo -= bval
                evento     = "Balão"
                # Recalcula PMT se modo RECALC e PRICE
                if p.pmt_apos_balao == "RECALC" and p.sistema == "PRICE":
                    prazo_rest = n - mes
                    if prazo_rest > 0 and novo_saldo > 0.01:
                        pmt_vigente = calcular_pmt_price(novo_saldo, tm, prazo_rest)
                        pmt_novo    = pmt_vigente

        fluxo.append(LinhaFluxo(
            mes=mes,
            saldo_inicial=saldo_ini,
            juros=juros,
            amortizacao=amort,
            pmt=pmt_mes,
            balao=balao_mes,
            correcao_saldo=correcao,
            saldo_final=max(novo_saldo, 0.0),
            pmt_novo=pmt_novo,
            evento=evento,
        ))

        saldo = max(novo_saldo, 0.0)
        if saldo <= 0.01:
            break

    return ResultadoCenario(premissas=p, fluxo=fluxo)


# ---------------------------------------------------------------------------
# Análise de Investimento
# ---------------------------------------------------------------------------

@dataclass
class AnaliseInvestimento:
    cenario: ResultadoCenario

    # --- Rent vs Buy ---
    def fluxo_rent_vs_buy(self) -> pd.DataFrame:
        """
        Compara:
        - Comprar: PMT + balões (saída de caixa) vs. patrimônio líquido acumulado
        - Alugar: aluguel crescente + rendimento do capital não imobilizado
        """
        p    = self.cenario.premissas
        rows = []

        # Taxa reajuste aluguel: se 0, usa IGP-M média 12m
        if p.reajuste_aluguel_aa > 0:
            rej_alug_aa = p.reajuste_aluguel_aa
        else:
            media_igpm = media_movel(p.indice_aluguel, 12)
            rej_alug_aa = (pow(1 + media_igpm / 100, 12) - 1) * 100

        rej_alug_m  = pow(1 + rej_alug_aa / 100, 1 / 12) - 1
        valz_m      = pow(1 + p.valorizacao_imovel_aa / 100, 1 / 12) - 1
        custo_op_m  = pow(1 + p.custo_oportunidade_aa / 100, 1 / 12) - 1
        vacancia_f  = 1 - p.vacancia_custos_pct / 100

        aluguel       = p.aluguel_atual
        valor_imovel  = p.valor_imovel
        # Quem aluga: tem o capital da entrada + vai acumulando diferença
        capital_alug  = p.entrada  # capital que NÃO foi imobilizado
        acum_alug     = 0.0        # patrimônio acumulado (cenário aluguel)

        for linha in self.cenario.fluxo:
            mes = linha.mes

            # Valor do imóvel corrigido
            valor_imovel *= (1 + valz_m)

            # Saída de caixa comprador: PMT + balão
            saida_compra = linha.pmt + linha.balao

            # Patrimônio líquido do comprador: valor_imovel - saldo_devedor
            patrim_compra = valor_imovel - linha.saldo_final

            # Aluguel deste mês (pago pelo locatário)
            alug_mes = aluguel * (1 + rej_alug_m) ** (mes - 1)

            # Quem aluga: economiza a diferença entre PMT e aluguel, investe
            economizado = saida_compra - alug_mes
            capital_alug *= (1 + custo_op_m)
            capital_alug += economizado  # pode ser negativo (PMT < aluguel)

            # Receita líquida do imóvel (se locado — perspectiva do investidor)
            receita_liq = alug_mes * vacancia_f

            rows.append({
                'Mês': mes,
                'Aluguel': alug_mes,
                'PMT + Balão': saida_compra,
                'Saldo Devedor': linha.saldo_final,
                'Valor Imóvel': valor_imovel,
                'Patrim. Comprador': patrim_compra,
                'Capital Aluguel': capital_alug,
                'Receita Líq. Imóvel': receita_liq,
                'Diferença (Compra-Aluguel)': saida_compra - alug_mes,
            })

        return pd.DataFrame(rows)

    def ponto_equilibrio(self) -> Optional[int]:
        """Mês em que patrimônio do comprador supera capital do locatário."""
        df = self.fluxo_rent_vs_buy()
        cross = df[df['Patrim. Comprador'] >= df['Capital Aluguel']]
        if cross.empty:
            return None
        return int(cross.iloc[0]['Mês'])

    def vpl_financiamento(self) -> float:
        """
        VPL dos fluxos de saída do financiamento, descontados pela taxa de oportunidade.
        VPL negativo = custo líquido atual do financiamento.
        """
        p  = self.cenario.premissas
        td = pow(1 + p.taxa_desconto_vpl / 100, 1 / 12) - 1

        # Fluxo: entrada (mês 0) + PMTs + balões
        fluxos = [-p.entrada]
        for linha in self.cenario.fluxo:
            fluxos.append(-(linha.pmt + linha.balao))

        vpl = sum(f / pow(1 + td, t) for t, f in enumerate(fluxos))
        return vpl

    def tir_imovel(self) -> Optional[float]:
        """
        TIR do investimento imobiliário:
        Entrada: -entrada e -PMTs/balões (saídas)
        Saída final: valor do imóvel projetado no prazo efetivo
        Retorna TIR anual (%).
        """
        p     = self.cenario.premissas
        n     = self.cenario.prazo_efetivo
        valz  = pow(1 + p.valorizacao_imovel_aa / 100, n / 12) - 1
        val_final = p.valor_imovel * (1 + valz)

        # Fluxos mensais
        fluxos = [-p.entrada]
        for i, linha in enumerate(self.cenario.fluxo):
            saida = -(linha.pmt + linha.balao)
            if i == len(self.cenario.fluxo) - 1:
                saida += val_final  # recebe o imóvel no último mês
            fluxos.append(saida)

        try:
            tir_m = _tir_mensal(fluxos)
            if tir_m is None:
                return None
            return (pow(1 + tir_m, 12) - 1) * 100
        except Exception:
            return None

    def custo_oportunidade(self) -> dict:
        """
        Compara: investir os mesmos recursos (entrada + PMTs + balões)
        em renda fixa (LCI/CDI) vs. comprar o imóvel.
        """
        p        = self.cenario.premissas
        co_m     = pow(1 + p.custo_oportunidade_aa / 100, 1 / 12) - 1
        n        = self.cenario.prazo_efetivo
        valz     = pow(1 + p.valorizacao_imovel_aa / 100, n / 12) - 1
        val_final = p.valor_imovel * (1 + valz)

        # Acumula cada saída de caixa do financiamento em renda fixa
        acumulado = p.entrada  # entrada no mês 0
        for i, linha in enumerate(self.cenario.fluxo):
            acumulado *= (1 + co_m)
            acumulado += (linha.pmt + linha.balao)

        total_investido = p.entrada + self.cenario.total_pmt + self.cenario.total_balao

        return {
            'total_investido_financiamento': total_investido,
            'patrimonio_renda_fixa': acumulado,
            'valor_imovel_final': val_final,
            'patrimonio_liquido_imovel': val_final,  # já quitado
            'vantagem_imovel': val_final - acumulado,
            'prazo_meses': n,
        }

    def cap_rate(self) -> float:
        """Cap Rate anual bruto: aluguel anual / valor imóvel."""
        return (self.cenario.premissas.aluguel_atual * 12) / self.cenario.premissas.valor_imovel * 100

    def yield_liquido(self) -> float:
        """Yield líquido anual considerando vacância e custos."""
        p   = self.cenario.premissas
        vac = 1 - p.vacancia_custos_pct / 100
        return (p.aluguel_atual * 12 * vac) / p.valor_imovel * 100

    def break_even_valorizacao(self) -> float:
        """
        Valorização anual mínima que o imóvel precisa para igualar
        o total pago com o valor final.
        """
        n  = self.cenario.prazo_efetivo
        tp = self.cenario.total_pago
        vi = self.cenario.premissas.valor_imovel
        # vi * (1+x)^(n/12) = tp  →  x = (tp/vi)^(12/n) - 1
        if vi <= 0 or n <= 0:
            return 0.0
        return (pow(tp / vi, 12 / n) - 1) * 100


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _tir_mensal(fluxos: list, tol: float = 1e-8, max_iter: int = 1000) -> Optional[float]:
    """Newton-Raphson para TIR mensal."""
    r = 0.01
    for _ in range(max_iter):
        f  = sum(c / pow(1 + r, t) for t, c in enumerate(fluxos))
        df = sum(-t * c / pow(1 + r, t + 1) for t, c in enumerate(fluxos))
        if abs(df) < 1e-12:
            return None
        r_new = r - f / df
        if abs(r_new - r) < tol:
            return r_new
        r = r_new
    return None


# ---------------------------------------------------------------------------
# Helpers de balão para UI
# ---------------------------------------------------------------------------

def baloes_fixos(valor: float, freq: int, primeiro: int, n_max: int) -> List[Balao]:
    baloes = []
    for i in range(n_max):
        mes = primeiro + i * freq
        baloes.append(Balao(mes=mes, valor=valor))
    return baloes


def baloes_custom(texto_linhas: List[str]) -> List[Balao]:
    """Parseia lista de strings 'MÊS/VALOR'."""
    baloes = []
    for linha in texto_linhas:
        linha = linha.strip()
        if '/' in linha:
            partes = linha.split('/')
            try:
                mes = int(partes[0].strip())
                val = float(partes[1].strip().replace(',', '.'))
                if mes > 0 and val > 0:
                    baloes.append(Balao(mes=mes, valor=val))
            except ValueError:
                pass
    return sorted(baloes, key=lambda b: b.mes)
