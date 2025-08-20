import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px
import tempfile
import os
import requests
import json
import time
from playwright.sync_api import sync_playwright

# ==============================================
# CONFIGURAÇÃO INICIAL DO APP
# ==============================================
st.set_page_config(layout="wide", page_title="Agência Referência TikTok")

# ==============================================
# CSS para Estilização
# ==============================================
st.markdown(
    """
<style>
    /* Estilo geral */
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #333333;
        background-color: #f0f2f6;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        padding-left: 5%;
        padding-right: 5%;
    }
    h1, h2, h3, h4 {
        color: #1a1a1a;
        font-weight: 600;
        margin-top: 1.5em;
        margin-bottom: 0.5em;
    }
    .stButton > button {
        background-color: #4CAF50;
        color: white;
        border-radius: 8px;
        padding: 10px 20px;
        font-size: 16px;
        font-weight: bold;
        transition: all 0.3s ease;
        border: none;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .stButton > button:hover {
        background-color: #45a049;
        transform: translateY(-2px);
        box-shadow: 0 6px 8px rgba(0, 0, 0, 0.15);
    }
    /* Estilo para as colunas de KPIs */
    .st-emotion-cache-1uj251k {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
</style>
""", unsafe_allow_html=True
)

# ...existing code...
def convert_to_int(text):
    """Converte texto do TikTok (ex: '1.2M') para inteiro."""
    text = text.replace(',', '').replace('.', '')
    if 'K' in text:
        return int(float(text.replace('K', '')) * 1000)
    elif 'M' in text:
        return int(float(text.replace('M', '')) * 1000000)
    elif 'B' in text:
        return int(float(text.replace('B', '')) * 1000000000)
    else:
        try:
            return int(text)
        except:
            return 0

def estimate_earnings(views):
    """Estimativa simples de ganhos baseada em visualizações."""
    # Ajuste conforme sua lógica
    return views * 0.01
# ...existing code...

# ==============================================
# BANCO DE DADOS
# ==============================================
def init_db():
    """Inicializa o banco de dados e cria as tabelas necessárias."""
    try:
        conn = sqlite3.connect("influencers.db", check_same_thread=False)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE,
            senha TEXT,
            tipo TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            influencer TEXT,
            tipo TEXT,
            valor INTEGER,
            data TEXT,
            metodo TEXT,
            ganhos REAL,
            live_curtidas INTEGER,
            live_visualizacoes INTEGER
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos_live (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            influencer TEXT,
            nome_produto TEXT,
            valor_estimado REAL,
            data TEXT
        )
        """)

        # Adiciona colunas se não existirem
        try:
            cursor.execute("ALTER TABLE historico ADD COLUMN ganhos REAL")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE historico ADD COLUMN live_curtidas INTEGER")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE historico ADD COLUMN live_visualizacoes INTEGER")
        except sqlite3.OperationalError:
            pass

        # Adiciona ou atualiza usuários de login
        cursor.execute("INSERT OR IGNORE INTO usuarios (usuario, senha, tipo) VALUES (?, ?, ?)",
                       ('admin', 'alfa@01admin', 'criador'))
        cursor.execute("INSERT OR IGNORE INTO usuarios (usuario, senha, tipo) VALUES (?, ?, ?)",
                       ('dev', 'dev@123', 'criador'))

        conn.commit()
        return conn, cursor

    except Exception as e:
        st.error(f"Erro ao inicializar banco de dados: {str(e)}")
        return None, None


conn, cursor = init_db()


# ==============================================
# CONFIGURAÇÃO DO PLAYWRIGHT E NAVEGADOR
# ==============================================
def setup_playwright():
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    return p, browser

# ==============================================
# FUNÇÕES DE SCRAPING
# ==============================================
def get_tiktok_data_from_scraping(username):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"
            )
            page = context.new_page()

            st.info(f"Conectando ao TikTok para buscar dados de @{username}...")
            page.goto(f"https://www.tiktok.com/@{username}", timeout=120000)

            followers_elem = page.locator("xpath=//strong[@data-e2e='followers-count']")
            likes_elem = page.locator("xpath=//strong[@data-e2e='likes-count']")

            # Wait for elements to be visible
            followers_elem.wait_for(state="visible")
            likes_elem.wait_for(state="visible")

            followers_num = convert_to_int(followers_elem.inner_text())
            likes_num = convert_to_int(likes_elem.inner_text())
            views_num = likes_num

            return {
                'seguidores': followers_num,
                'curtidas': likes_num,
                'visualizacoes': views_num
            }

    except TimeoutError:
        st.error("Erro: O tempo limite para carregar a página ou encontrar elementos foi excedido. O influencer pode não existir ou a conexão está lenta.")
        return None
    except PlaywrightError as e:
        st.error(f"Erro do Playwright. Verifique a página do influencer. Erro: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Erro inesperado no scraping: {str(e)}")
        return None

# ...existing code...
conn, cursor = init_db()

# ==============================================
# FUNÇÕES UTILITÁRIAS
# ==============================================
def convert_to_int(text):
    """Converte texto do TikTok (ex: '1.2M') para inteiro."""
    text = text.replace(',', '').replace('.', '')
    if 'K' in text:
        return int(float(text.replace('K', '')) * 1000)
    elif 'M' in text:
        return int(float(text.replace('M', '')) * 1000000)
    elif 'B' in text:
        return int(float(text.replace('B', '')) * 1000000000)
    else:
        try:
            return int(text)
        except:
            return 0

def estimate_earnings(views):
    """Estimativa simples de ganhos baseada em visualizações."""
    # Ajuste conforme sua lógica
    return views * 0.01

# ==============================================
# CONFIGURAÇÃO DO PLAYWRIGHT PARA AMBIENTES HEADLESS
# ==============================================
def setup_playwright():
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    return p, browser
# ...existing code...
# ==============================================
# FUNÇÕES DO APLICATIVO
# ==============================================
def verificar_login(usuario, senha):
    try:
        cursor.execute("SELECT * FROM usuarios WHERE usuario=? AND senha=?", (usuario, senha))
        return cursor.fetchone()
    except Exception as e:
        st.error(f"Erro ao verificar login: {str(e)}")
        return None


def adicionar_registro(usuario, influencer, tipo, valor, metodo, live_curtidas=0, live_visualizacoes=0):
    try:
        data = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ganhos_estimados = estimate_earnings(valor)
        cursor.execute("""
        INSERT INTO historico (usuario, influencer, tipo, valor, data, metodo, ganhos, live_curtidas, live_visualizacoes) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (usuario, influencer, tipo, valor, data, metodo, ganhos_estimados, live_curtidas, live_visualizacoes))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar registro: {str(e)}")
        return False


def check_monthly_live_scrape(influencer, usuario):
    cursor.execute("""
    SELECT data FROM historico
    WHERE influencer = ? AND usuario = ? AND live_visualizacoes > 0
    ORDER BY data DESC LIMIT 1
    """, (influencer, usuario))
    last_scrape = cursor.fetchone()

    if last_scrape:
        last_date = datetime.strptime(last_scrape[0], "%Y-%m-%d %H:%M:%S")
        if last_date.month == datetime.now().month and last_date.year == datetime.now().year:
            return False
    return True


def adicionar_produto_live(influencer, nome_produto, valor_estimado):
    try:
        data = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
        INSERT INTO produtos_live (influencer, nome_produto, valor_estimado, data)
        VALUES (?, ?, ?, ?)
        """, (influencer, nome_produto, valor_estimado, data))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar produto: {str(e)}")
        return False


def get_produtos_ganhados(influencers, data_inicio, data_fim):
    try:
        query = """
        SELECT influencer, nome_produto, valor_estimado, data
        FROM produtos_live
        WHERE influencer IN ({}) AND data >= ? AND data <= ?
        """.format(','.join(['?'] * len(influencers)))

        params = influencers + [data_inicio.strftime("%Y-%m-%d 00:00:00"), data_fim.strftime("%Y-%m-%d 23:59:59")]

        df = pd.read_sql_query(query, conn, params=params)
        return df
    except Exception as e:
        st.error(f"Erro ao buscar produtos: {str(e)}")
        return pd.DataFrame()


def exportar_excel(df, filename="relatorio.xlsx"):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            df.to_excel(tmp.name, index=False)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as f:
            st.download_button(
                "📊 Exportar para Excel",
                f,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        os.unlink(tmp_path)
    except Exception as e:
        st.error(f"Erro ao exportar arquivo: {str(e)}")


# ==============================================
# INTERFACES DO USUÁRIO
# ==============================================
def login_section():
    st.title("Login")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Acesse"):
        if not usuario or not senha:
            st.warning("Por gentileza, preencha todos os campos")
            return

        usuario_db = verificar_login(usuario, senha)
        if usuario_db:
            st.session_state.logged_in = True
            st.session_state.usuario = usuario
            st.session_state.tipo_usuario = usuario_db[3]
            st.success("Login realizado com sucesso!")
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos")


def main_app():
    st.title(f"Bem-vindo, ao gerenciamento de carreira de tiktokers {st.session_state.usuario}!")

    st.header("1. Buscar e Adicionar Influencer")
    influencer = st.text_input("Nome do influencer (sem @)", placeholder="ex: simoneses")

    if st.button("Buscar Dados e Salvar"):
        if not influencer:
            st.warning("Por favor, digite o nome do influencer.")
        else:
            with st.spinner(f"Buscando dados de @{influencer}..."):
                dados = get_tiktok_data_from_scraping(influencer)

                live_data = {'live_curtidas': 0, 'live_visualizacoes': 0}
                if check_monthly_live_scrape(f"@{influencer}", st.session_state.usuario):
                    live_data = get_live_data_from_scraping(influencer)
                else:
                    st.info(f"A verificação de lives para @{influencer} já foi realizada este mês. Pulando esta etapa.")

                if dados:
                    salvo_seguidores = adicionar_registro(st.session_state.usuario, f"@{influencer}", 'seguidores',
                                                          dados['seguidores'], 'Scraping',
                                                          live_data['live_curtidas'], live_data['live_visualizacoes'])
                    salvo_curtidas = adicionar_registro(st.session_state.usuario, f"@{influencer}", 'curtidas',
                                                        dados['curtidas'], 'Scraping')
                    salvo_visualizacoes = adicionar_registro(st.session_state.usuario, f"@{influencer}",
                                                             'visualizacoes', dados['visualizacoes'], 'Scraping')
                    salvo_ganhos = adicionar_registro(st.session_state.usuario, f"@{influencer}", 'ganhos',
                                                      estimate_earnings(dados['visualizacoes']), 'Estimativa')

                    if salvo_seguidores and salvo_curtidas and salvo_visualizacoes and salvo_ganhos:
                        st.success(f"Dados de @{influencer} salvos com sucesso!")
                        st.write(f"**Seguidores:** {dados['seguidores']:,}")
                        st.write(f"**Curtidas:** {dados['curtidas']:,}")
                        st.write(f"**Visualizações:** {dados['visualizacoes']:,}")
                        st.write(f"**Ganhos Estimados (R$):** R$ {estimate_earnings(dados['visualizacoes']):,.2f}")
                        if live_data['live_visualizacoes'] > 0:
                            st.write(f"**Live Curtidas:** {live_data['live_curtidas']:,}")
                            st.write(f"**Live Visualizações:** {live_data['live_visualizacoes']:,}")
                    else:
                        st.error("Erro ao salvar os dados no banco.")
                else:
                    st.error("Não foi possível obter os dados do influencer. Verifique o nome ou tente novamente.")

    st.header("2. Análise do Histórico de Influencers")
    influencers_disponiveis = pd.read_sql_query(
        "SELECT DISTINCT influencer FROM historico WHERE usuario = ?", conn, params=[st.session_state.usuario]
    )['influencer'].tolist()

    if not influencers_disponiveis:
        st.info("Nenhum influencer encontrado no histórico. Use a seção acima para adicionar um.")

    else:
        col_filtros1, col_filtros2 = st.columns([2, 1])

        with col_filtros1:
            influencers_selecionados = st.multiselect("Selecione os Influencers para Análise:", influencers_disponiveis)
        with col_filtros2:
            escala_unidade = st.selectbox("Escala de Visualização dos Gráficos",
                                          options=["Unidades", "Milhares (K)", "Dez Milhares (10K)",
                                                   "Cem Milhares (100K)"])

        col_data_inicio, col_data_fim = st.columns(2)
        with col_data_inicio:
            data_inicio = st.date_input("Data de Início", datetime.now() - timedelta(days=30))
        with col_data_fim:
            data_fim = st.date_input("Data de Fim", datetime.now())

        if st.button("Gerar Análise"):
            if not influencers_selecionados:
                st.warning("Por favor, selecione ao menos um influencer.")
            else:
                query = """
                SELECT influencer, tipo, valor, data, ganhos, live_curtidas, live_visualizacoes
                FROM historico
                WHERE usuario = ? AND data >= ? AND data <= ? AND influencer IN ({})
                """.format(','.join(['?'] * len(influencers_selecionados)))

                params = [st.session_state.usuario, data_inicio.strftime("%Y-%m-%d 00:00:00"),
                          data_fim.strftime("%Y-%m-%d 23:59:59")] + influencers_selecionados

                df = pd.read_sql_query(query, conn, params=params)

                if not df.empty:
                    df['data'] = pd.to_datetime(df['data'])
                    df = df.sort_values(by=['influencer', 'data'])

                    escala = 1
                    unidade_label = ""
                    if escala_unidade == "Milhares (K)":
                        escala = 1000
                        unidade_label = " (em Milhares)"
                    elif escala_unidade == "Dez Milhares (10K)":
                        escala = 10000
                        unidade_label = " (em Dez Milhares)"
                    elif escala_unidade == "Cem Milhares (100K)":
                        escala = 100000
                        unidade_label = " (em Cem Milhares)"

                    df['valor_escala'] = df['valor'] / escala
                    df['ganhos_escala'] = df['ganhos'] / escala

                    st.subheader("Resumo do Crescimento no Período")
                    crescimento_df = pd.DataFrame()

                    for influencer in influencers_selecionados:
                        temp_df = df[df['influencer'] == influencer]
                        if not temp_df.empty:
                            crescimentos = {}
                            for tipo in ['seguidores', 'curtidas', 'visualizacoes']:
                                df_tipo = temp_df[temp_df['tipo'] == tipo]
                                if not df_tipo.empty:
                                    start_value = df_tipo['valor'].iloc[0]
                                    end_value = df_tipo['valor'].iloc[-1]
                                    crescimento = end_value - start_value
                                    crescimento_percentual = ((
                                                                      end_value - start_value) / start_value) * 100 if start_value != 0 else 0
                                    crescimentos[tipo] = crescimento
                                    crescimentos[f'{tipo}_percentual'] = crescimento_percentual
                                else:
                                    crescimentos[tipo] = 0
                                    crescimentos[f'{tipo}_percentual'] = 0

                            df_ganhos = temp_df[temp_df['tipo'] == 'ganhos']
                            if not df_ganhos.empty:
                                start_ganhos = df_ganhos['valor'].iloc[0]
                                end_ganhos = df_ganhos['valor'].iloc[-1]
                                crescimento_ganhos = end_ganhos - start_ganhos
                                crescimento_ganhos_percentual = ((
                                                                         end_ganhos - start_ganhos) / start_ganhos) * 100 if start_ganhos != 0 else 0
                            else:
                                crescimento_ganhos = 0
                                crescimento_ganhos_percentual = 0

                            crescimento_df = pd.concat(
                                [crescimento_df,
                                 pd.DataFrame(
                                     [{'influencer': influencer, **crescimentos, 'ganhos': crescimento_ganhos,
                                       'ganhos_percentual': crescimento_ganhos_percentual}])],
                                ignore_index=True)

                    if not crescimento_df.empty:
                        for index, row in crescimento_df.iterrows():
                            st.write(f"### {row['influencer']}")
                            col_seg, col_cur, col_vis, col_ganhos = st.columns(4)
                            with col_seg:
                                st.metric("Novos Seguidores", f"{row['seguidores']:,}",
                                          f"{row['seguidores_percentual']:.2f}%")
                            with col_cur:
                                st.metric("Novas Curtidas", f"{row['curtidas']:,}",
                                          f"{row['curtidas_percentual']:.2f}%")
                            with col_vis:
                                st.metric("Novas Visualizações", f"{row['visualizacoes']:,}",
                                          f"{row['visualizacoes_percentual']:.2f}%")
                            with col_ganhos:
                                st.metric("Ganhos Estimados (R$)", f"R$ {row['ganhos']:,.2f}",
                                          f"{row['ganhos_percentual']:.2f}%")

                    st.subheader("Evolução das Métricas" + unidade_label)
                    df_filtrado_metrica = df[df['tipo'].isin(['seguidores', 'curtidas', 'visualizacoes'])]
                    fig_evolucao = px.line(df_filtrado_metrica, x='data', y='valor_escala', color='influencer',
                                           line_dash='tipo',
                                           title="Evolução de Seguidores, Curtidas e Visualizações")
                    fig_evolucao.update_layout(yaxis_tickformat='.2s')
                    fig_evolucao.update_traces(
                        hovertemplate='<b>%{fullData.name}</b><br>Data: %{x}<br>Valor: %{y:,.0f}' + unidade_label.replace(
                            " (", "").replace(")", ""))
                    st.plotly_chart(fig_evolucao, use_container_width=True)

                    # Novo gráfico de variação diária
                    st.subheader("Variação Diária de Seguidores e Curtidas")
                    df_seguidores = df[df['tipo'] == 'seguidores'].set_index('data')
                    df_curtidas = df[df['tipo'] == 'curtidas'].set_index('data')

                    df_seguidores_diff = df_seguidores.groupby('influencer')['valor'].diff().fillna(0)
                    df_curtidas_diff = df_curtidas.groupby('influencer')['valor'].diff().fillna(0)

                    df_variacao = pd.DataFrame({
                        'seguidores_diff': df_seguidores_diff,
                        'curtidas_diff': df_curtidas_diff,
                        'influencer': df_seguidores['influencer']
                    }).reset_index().melt(id_vars=['data', 'influencer'],
                                          value_vars=['seguidores_diff', 'curtidas_diff'],
                                          var_name='metrica',
                                          value_name='variacao')

                    fig_variacao = px.bar(df_variacao, x='data', y='variacao', color='influencer', barmode='group',
                                          facet_col='metrica', title="Variação Diária de Seguidores e Curtidas")
                    st.plotly_chart(fig_variacao, use_container_width=True)

                    st.subheader("Evolução de Ganhos Estimados (R$)" + unidade_label)
                    df_filtrado_ganhos = df[df['tipo'] == 'ganhos']
                    fig_ganhos = px.line(df_filtrado_ganhos, x='data', y='valor_escala', color='influencer',
                                         title="Evolução de Ganhos Estimados")
                    fig_ganhos.update_layout(yaxis_tickformat='.2s')
                    fig_ganhos.update_traces(
                        hovertemplate='<b>%{fullData.name}</b><br>Data: %{x}<br>Ganhos: R$ %{y:,.2f}')
                    st.plotly_chart(fig_ganhos, use_container_width=True)

                    st.subheader("Taxa de Engajamento por Influencer")
                    df_pivot = df.pivot_table(index='influencer', columns='tipo', values='valor',
                                              aggfunc='mean').reset_index()

                    if 'curtidas' in df_pivot.columns and 'seguidores' in df_pivot.columns:
                        df_pivot['taxa_engajamento_absoluta'] = (df_pivot['curtidas'] / df_pivot['seguidores']).fillna(
                            0)
                        df_engagement = df_pivot[['influencer', 'taxa_engajamento_absoluta']].round(4)

                        st.dataframe(df_engagement.rename(
                            columns={'taxa_engajamento_absoluta': 'Engajamento Absoluto (curtidas/seguidores)'}),
                            use_container_width=True)

                        # Ordena os influencers por engajamento
                        df_engagement_sorted = df_engagement.sort_values(by='taxa_engajamento_absoluta',
                                                                         ascending=False)

                        fig_engajamento = px.bar(df_engagement_sorted, x='influencer', y='taxa_engajamento_absoluta',
                                                 title="Taxa de Engajamento Média (Valor Absoluto)",
                                                 labels={
                                                     'taxa_engajamento_absoluta': 'Engajamento (curtidas/seguidores)',
                                                     'influencer': 'Influencer'})
                        st.plotly_chart(fig_engajamento, use_container_width=True)
                    else:
                        st.info(
                            "Para visualizar a taxa de engajamento, certifique-se de que o histórico inclui dados de 'seguidores' e 'curtidas'.")

                    st.subheader("Análise de Lives")
                    df_lives = df[
                        ['influencer', 'data', 'live_curtidas', 'live_visualizacoes']].drop_duplicates().dropna(
                        subset=['live_curtidas'])
                    if not df_lives.empty:
                        df_lives['mes'] = df_lives['data'].dt.to_period('M')
                        lives_por_mes = df_lives.groupby(['influencer', 'mes']).size().reset_index(
                            name='quantidade_lives')
                        lives_por_mes['mes'] = lives_por_mes['mes'].astype(str)

                        st.subheader("Quantidade de Lives por Mês")
                        fig_lives_mes = px.bar(lives_por_mes, x='mes', y='quantidade_lives', color='influencer',
                                               title="Quantidade de Lives Registradas por Mês")
                        st.plotly_chart(fig_lives_mes, use_container_width=True)

                        st.subheader("Visualizações e Curtidas em Lives")
                        # Modificação para ajustar a escala e o hover
                        df_lives['live_visualizacoes_k'] = df_lives['live_visualizacoes'] / 1000

                        fig_lives = px.scatter(df_lives, x='data', y='live_visualizacoes_k', color='influencer',
                                               size='live_curtidas',
                                               hover_data={
                                                   'live_visualizacoes': ':.0f',
                                                   'live_curtidas': ':.0f',
                                                   'live_visualizacoes_k': False
                                               },
                                               title="Visualizações e Curtidas em Lives por Período")

                        fig_lives.update_layout(
                            yaxis_title="Visualizações de Live (em milhares)",
                            hovermode="x unified"
                        )
                        st.plotly_chart(fig_lives, use_container_width=True)

                    else:
                        st.info("Nenhum dado de live encontrado para o período selecionado.")

                    exportar_excel(df, filename=f"relatorio_tiktok_{data_inicio}_{data_fim}.xlsx")
                else:
                    st.warning("Nenhum dado encontrado para os filtros selecionados.")

    # ---
    # SEÇÃO DE PRODUTOS GANHADOS
    # ---
    st.header("3. Gerenciamento de Produtos Ganhados em Live")

    if not influencers_disponiveis:
        st.info("Nenhum influencer encontrado no histórico. Adicione um na seção 1 para gerenciar produtos.")
    else:
        tab1, tab2 = st.tabs(["Adicionar Produto", "Consultar Produtos"])

        with tab1:
            st.subheader("Adicionar Produto Manualmente")
            influencer_produto = st.selectbox("Selecione o Influencer", influencers_disponiveis)
            nome_produto = st.text_input("Nome do Produto")
            valor_estimado = st.number_input("Valor Estimado (R$)", min_value=0.0, format="%.2f")

            if st.button("Adicionar Produto Ganhado"):
                if not nome_produto or valor_estimado <= 0:
                    st.warning("Por favor, preencha o nome do produto e o valor estimado.")
                else:
                    if adicionar_produto_live(influencer_produto, nome_produto, valor_estimado):
                        st.success(f"Produto '{nome_produto}' adicionado com sucesso para {influencer_produto}!")
                    else:
                        st.error("Falha ao adicionar o produto.")

        with tab2:
            st.subheader("Consultar Produtos Ganhados")
            influencers_consulta_prod = st.multiselect(
                "Selecione os Influencers para a Consulta de Produtos:",
                influencers_disponiveis
            )

            col_data_inicio_prod, col_data_fim_prod = st.columns(2)
            with col_data_inicio_prod:
                data_inicio_prod = st.date_input("Data de Início da Consulta", datetime.now() - timedelta(days=30),
                                                 key="data_inicio_prod")
            with col_data_fim_prod:
                data_fim_prod = st.date_input("Data de Fim da Consulta", datetime.now(), key="data_fim_prod")

            if st.button("Buscar Produtos Ganhados"):
                if not influencers_consulta_prod:
                    st.warning("Selecione pelo menos um influencer para a consulta.")
                else:
                    df_produtos = get_produtos_ganhados(
                        influencers_consulta_prod,
                        data_inicio_prod,
                        data_fim_prod
                    )

                    if not df_produtos.empty:
                        df_produtos['data'] = pd.to_datetime(df_produtos['data']).dt.strftime('%Y-%m-%d %H:%M:%S')
                        st.dataframe(df_produtos, use_container_width=True)
                        exportar_excel(df_produtos, filename="produtos_ganhados.xlsx")
                    else:
                        st.info("Nenhum produto encontrado para os influencers e período selecionados.")

    if st.sidebar.button("Sair"):
        st.session_state.clear()
        st.rerun()


# ==============================================
# EXECUÇÃO PRINCIPAL
# ==============================================
if 'logged_in' not in st.session_state:
    login_section()
else:
    main_app()