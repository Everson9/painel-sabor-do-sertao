import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Sabor do Sertão", layout="wide")
st.title("Painel de Vendas: Sabor do Sertão")

COR = "#1f6f8b"
DIAS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def reais(valor):
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def inteiro(valor):
    return f"{valor:,}".replace(",", ".")


@st.cache_data
def carregar(arquivo):
    return pd.read_csv(arquivo, parse_dates=["data"])


arquivo = st.sidebar.file_uploader("Envie o CSV de vendas", type="csv")
if arquivo is None:
    st.info("Envie o arquivo para começar.")
    st.stop()

df = carregar(arquivo)

aba_painel, aba_livre = st.tabs(["Painel de vendas", "Explorador livre"])

with aba_painel:
    # ---------------- Nível 1: exploração ----------------
    st.header("1. Exploração dos dados")
    st.subheader("Primeiras linhas")
    st.dataframe(
        df.head(10), width="stretch",
        column_config={"data": st.column_config.DateColumn("data", format="DD/MM/YYYY")},
    )

    col_desc, col_na = st.columns([3, 1])
    with col_desc:
        st.subheader("Resumo estatístico")
        st.dataframe(df.describe(include="number"), width="stretch")
    with col_na:
        st.subheader("Valores ausentes")
        ausentes = df.isna().sum().rename("ausentes").to_frame()
        st.dataframe(ausentes, width="stretch")

    mediana = df["avaliacao"].median()
    qtd_ausentes = int(df["avaliacao"].isna().sum())
    df["avaliacao"] = df["avaliacao"].fillna(mediana)
    st.caption(
        f"Tratamento de `avaliacao`: os {qtd_ausentes} valores ausentes foram "
        f"preenchidos com a mediana ({mediana:.0f}). Não removemos as linhas porque "
        "elas são vendas reais e entram no faturamento; apagar tiraria dinheiro do "
        "painel. Escolhemos a mediana em vez da média porque a avaliação é uma nota "
        "inteira de 1 a 5: a mediana é uma nota que existe na escala e não é puxada "
        "por valores extremos."
    )

# ---------------- Nível 3: filtros (barra lateral) ----------------
st.sidebar.header("Filtros")
cidades = sorted(df["cidade"].unique())
categorias = sorted(df["categoria"].unique())
filtro_cidades = st.sidebar.multiselect("Cidade", cidades, default=cidades)
filtro_categorias = st.sidebar.multiselect("Categoria", categorias, default=categorias)
data_min, data_max = df["data"].min().date(), df["data"].max().date()
periodo = st.sidebar.date_input(
    "Intervalo de datas",
    value=(data_min, data_max),
    min_value=data_min,
    max_value=data_max,
)
# Enquanto o usuário escolhe, o date_input devolve só a data inicial.
if len(periodo) == 2:
    inicio, fim = periodo
elif len(periodo) == 1:
    inicio, fim = periodo[0], data_max
else:
    inicio, fim = data_min, data_max

filtrado = df[
    df["cidade"].isin(filtro_cidades)
    & df["categoria"].isin(filtro_categorias)
    & df["data"].dt.date.between(inicio, fim)
]



def painel(filtrado):
    if filtrado.empty:
        st.warning("Nenhuma venda com esses filtros. Ajuste a barra lateral.")
        return

    # ---------------- Nível 2: indicadores ----------------
    st.header("2. Indicadores")
    st.caption(
        f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y} · {len(filtro_cidades)} cidade(s) · "
        f"{len(filtro_categorias)} categoria(s)"
    )
    faturamento = filtrado["total"].sum()
    vendas = len(filtrado)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Faturamento total", reais(faturamento))
    k2.metric("Número de vendas", inteiro(vendas))
    k3.metric("Ticket médio", reais(faturamento / vendas))
    k4.metric("Avaliação média", f"{filtrado['avaliacao'].mean():.2f} / 5".replace(".", ","))

    # ---------------- Nível 4: gráficos ----------------
    st.header("3. Gráficos")
    g1, g2, g3, g4, g5 = st.tabs(
        ["Faturamento mensal", "Por cidade", "Top 5 produtos", "Pagamento", "Dia x hora"]
    )

    with g1:
        mensal = filtrado.groupby(filtrado["data"].dt.to_period("M"))["total"].sum()
        mensal.index = mensal.index.astype(str)
        mensal = mensal.reset_index().rename(columns={"data": "mes"})
        fig = px.line(
            mensal, x="mes", y="total", markers=True,
            title="Faturamento mensal",
            labels={"mes": "Mês", "total": "Faturamento (R$)"},
        )
        fig.update_traces(line_color=COR, line_width=2, marker_size=8)
        st.plotly_chart(fig, width="stretch")

    with g2:
        por_cidade = filtrado.groupby("cidade")["total"].sum().sort_values(ascending=False)
        fig = px.bar(
            por_cidade.reset_index(), x="cidade", y="total",
            title="Faturamento por cidade", text_auto=".3s",
            labels={"cidade": "Cidade", "total": "Faturamento (R$)"},
        )
        fig.update_traces(marker_color=COR)
        st.plotly_chart(fig, width="stretch")

    with g3:
        top5 = filtrado.groupby("produto")["quantidade"].sum().nlargest(5).sort_values()
        fig = px.bar(
            top5.reset_index(), x="quantidade", y="produto", orientation="h",
            title="Top 5 produtos mais vendidos (unidades)", text_auto=True,
            labels={"produto": "Produto", "quantidade": "Unidades vendidas"},
        )
        fig.update_traces(marker_color=COR)
        st.plotly_chart(fig, width="stretch")

    with g4:
        pagamento = filtrado["pagamento"].value_counts(normalize=True).mul(100).sort_values()
        fig = px.bar(
            pagamento.reset_index(), x="proportion", y="pagamento", orientation="h",
            title="Participação de cada forma de pagamento (% das vendas)",
            text_auto=".1f",
            labels={"pagamento": "Forma de pagamento", "proportion": "% das vendas"},
        )
        fig.update_traces(marker_color=COR)
        st.plotly_chart(fig, width="stretch")

    with g5:
        calor = filtrado.assign(dia=filtrado["data"].dt.dayofweek.map(dict(enumerate(DIAS))))
        fig = px.density_heatmap(
            calor, x="hora", y="dia",
            title="Número de vendas por dia da semana e hora",
            category_orders={"dia": DIAS}, nbinsx=15,
            color_continuous_scale="Blues",
            labels={"hora": "Hora do dia", "dia": "Dia da semana"},
        )
        fig.update_layout(coloraxis_colorbar_title="Vendas")
        st.plotly_chart(fig, width="stretch")

    # ---------------- Nível 5: insights e exportação ----------------
    st.header("4. Insights")
    st.caption("Calculados a partir dos dados filtrados: mudam junto com a barra lateral.")

    cidade_lider = por_cidade.index[0]
    fatia_lider = por_cidade.iloc[0] / faturamento * 100
    cat = filtrado.groupby("categoria")["total"].sum().sort_values(ascending=False)
    fatia_cat = cat.iloc[0] / faturamento * 100
    pix = filtrado["pagamento"].value_counts(normalize=True)
    hora_pico = filtrado.groupby("hora").size().idxmax()
    vendas_pico = filtrado.groupby("hora").size().max()
    media_hora = filtrado.groupby("hora").size().mean()

    st.markdown(
        f"""
1. **Onde vendemos mais:** {cidade_lider} responde por {fatia_lider:.0f}% do
   faturamento ({reais(por_cidade.iloc[0])}). É a loja que mais pesa no resultado,
   então falta de estoque ou de equipe lá custa mais que em qualquer outra.
2. **O que dá mais dinheiro:** a categoria {cat.index[0]} traz {fatia_cat:.0f}% do
   faturamento. Já o produto que mais sai em unidades é {top5.index[-1]}:
   giro alto não é o mesmo que receita alta, e o cardápio deve ser pensado nos dois.
3. **Como os clientes pagam:** {pix.index[0]} é a forma mais usada
   ({pix.iloc[0] * 100:.0f}% das vendas). Vale priorizar maquininha e QR code
   funcionando bem e negociar a taxa desse meio primeiro.
4. **Quando vendemos mais:** o horário com mais vendas é às {hora_pico}h
   ({inteiro(int(vendas_pico))} vendas contra uma média de {media_hora:.0f} por hora).
   É o horário para reforçar a escala de atendentes.
"""
    )

    st.download_button(
        "Baixar CSV filtrado",
        data=filtrado.assign(data=filtrado["data"].dt.strftime("%Y-%m-%d"))
        .to_csv(index=False).encode("utf-8"),
        file_name="vendas_filtradas.csv",
        mime="text/csv",
    )

with aba_painel:
    painel(filtrado)

# ---------------- Bônus: explorador livre ----------------
with aba_livre:
    st.header("Explorador livre")
    st.write("Envie qualquer CSV (ou use o de vendas já carregado) e monte o gráfico.")
    outro = st.file_uploader("CSV para explorar", type="csv", key="livre")
    base = pd.read_csv(outro) if outro is not None else df
    colunas = list(base.columns)
    numericas = list(base.select_dtypes("number").columns)

    tipo = st.selectbox("Tipo de gráfico", ["Barras", "Linha", "Dispersão", "Histograma"])
    c1, c2 = st.columns(2)
    eixo_x = c1.selectbox("Eixo X", colunas)
    if tipo == "Histograma":
        eixo_y = None
        c2.selectbox("Eixo Y", ["(contagem)"], disabled=True)
    elif not numericas:
        st.warning("Esse CSV não tem coluna numérica para o eixo Y.")
        st.stop()
    else:
        eixo_y = c2.selectbox("Eixo Y", numericas)

    titulo = f"{eixo_y} por {eixo_x}" if eixo_y else f"Distribuição de {eixo_x}"
    if tipo in ("Barras", "Linha") and eixo_y != eixo_x:
        # Agrupa pelo X e soma o Y para não desenhar uma barra por linha do CSV.
        dados = base.groupby(eixo_x, as_index=False)[eixo_y].sum()
        grafico = px.bar if tipo == "Barras" else px.line
        fig = grafico(dados, x=eixo_x, y=eixo_y, title=f"Soma de {titulo}")
    elif tipo == "Dispersão" or tipo in ("Barras", "Linha"):
        fig = px.scatter(base, x=eixo_x, y=eixo_y, title=titulo)
    else:
        fig = px.histogram(base, x=eixo_x, title=titulo)
    if tipo == "Linha":
        fig.update_traces(line_color=COR)
    else:
        fig.update_traces(marker_color=COR)
    st.plotly_chart(fig, width="stretch")
