# -*- coding: utf-8 -*-
# app.py — Monitor de Influencers (TikTok, YouTube, Kwai)
# Rodar: streamlit run app.py --server.address 0.0.0.0 --server.port 8501

import os
import shutil
import tempfile
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import sqlite3
import streamlit as st

# ==== Selenium (multinavegador, sem webdriver_manager) =======================
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# -----------------------------------------------------------------------------
# CONFIG STREAMLIT
# -----------------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="Gerenciamento de Influencers")

SAFE_RERUN = getattr(st, "rerun", getattr(st, "experimental_rerun", None))

# -----------------------------------------------------------------------------
# BANCO DE DADOS (SQLite)
# -----------------------------------------------------------------------------
DB_PATH = os.environ.get("INFLUENCERS_DB", "influencers.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT UNIQUE NOT NULL,
        senha TEXT NOT NULL,
        tipo  TEXT DEFAULT 'criador'
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS historico_metricas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_app TEXT NOT NULL,
        plataforma   TEXT NOT NULL,
        influencer   TEXT NOT NULL,
        data         TEXT NOT NULL,
        seguidores   INTEGER,
        curtidas     INTEGER,
        visualizacoes INTEGER,
        joias        INTEGER
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS presentes_catalogo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL,
        valor_moedas INTEGER NOT NULL
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS presentes_recebidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        influencer TEXT NOT NULL,
        plataforma TEXT NOT NULL,
        data TEXT NOT NULL,
        presente_id INTEGER NOT NULL,
        quantidade INTEGER NOT NULL,
        FOREIGN KEY(presente_id) REFERENCES presentes_catalogo(id)
    )""")
    # usuário padrão
    cursor.execute("INSERT OR IGNORE INTO usuarios (usuario, senha, tipo) VALUES (?,?,?)",
                   ("admin", "alfa@01admin", "criador"))
    conn.commit()

init_db()

# -----------------------------------------------------------------------------
# AUTENTICAÇÃO
# -----------------------------------------------------------------------------
def login_user(usuario, senha):
    cursor.execute("SELECT usuario, senha, tipo FROM usuarios WHERE usuario=? AND senha=?", (usuario, senha))
    return cursor.fetchone()

def add_user(usuario, senha, tipo="criador"):
    try:
        cursor.execute("INSERT INTO usuarios (usuario, senha, tipo) VALUES (?, ?, ?)", (usuario, senha, tipo))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

# -----------------------------------------------------------------------------
# SELENIUM: DETECÇÃO DE NAVEGADOR (Chrome/Chromium ou Firefox)
# Usa Selenium Manager (Selenium >= 4.10) — não precisa webdriver_manager
# -----------------------------------------------------------------------------
def make_chrome_driver(headless=True):
    options = ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--incognito")
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Se seu provedor define caminho do Chrome:
    chrome_path = os.getenv("CHROME_PATH") or os.getenv("GOOGLE_CHROME_SHIM")
    if chrome_path:
        options.binary_location = chrome_path
    else:
        # tenta localizar automaticamente
        c = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
        if c:
            options.binary_location = c

    # Service() sem path -> Selenium Manager resolve driver
    service = ChromeService()
    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
        )
    except Exception:
        pass
    return driver

def make_firefox_driver(headless=True):
    options = FirefoxOptions()
    if headless:
        options.add_argument("--headless")
    options.set_preference("dom.webdriver.enabled", False)
    service = FirefoxService()  # Selenium Manager resolve o geckodriver
    driver = webdriver.Firefox(service=service, options=options)
    return driver

def get_driver():
    # tenta Chrome/Chromium, cai para Firefox
    try:
        return make_chrome_driver()
    except Exception:
        return make_firefox_driver()

# -----------------------------------------------------------------------------
# UTILIDADES
# -----------------------------------------------------------------------------
def to_int(s):
    if s is None:
        return None
    t = str(s).strip().lower().replace("\xa0", "")
    t = t.replace(".", "").replace(",", "")
    t = t.replace("mi", "m").replace("mil", "k")
    try:
        if t.endswith("k"):
            return int(float(t[:-1]) * 1_000)
        if t.endswith("m"):
            return int(float(t[:-1]) * 1_000_000)
        return int(t)
    except Exception:
        return None

# -----------------------------------------------------------------------------
# SCRAPERS (simples e tolerantes a mudanças de layout)
# Observação: plataformas mudam de layout com frequência; estes seletores
# funcionam hoje, mas oferecemos fallback e edição manual de métricas/presentes.
# -----------------------------------------------------------------------------
def scrape_tiktok(username: str, timeout=25):
    """Retorna dicionário com seguidores, curtidas, (visualizações estimadas) e joias (se visível)."""
    driver = None
    try:
        driver = get_driver()
        driver.set_page_load_timeout(timeout)
        url = f"https://www.tiktok.com/@{username}"
        st.info(f"TikTok: abrindo {url}")
        driver.get(url)
        wait = WebDriverWait(driver, timeout)

        # aceitar cookies se aparecer
        try:
            btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Accept') or contains(.,'Aceitar')]")))
            btn.click()
        except Exception:
            pass

        followers_el = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//strong[@data-e2e='followers-count' or contains(@title,'Followers') or contains(@aria-label,'Followers')]")
        ))
        likes_el = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//strong[@data-e2e='likes-count' or contains(@title,'Likes') or contains(@aria-label,'Likes')]")
        ))

        seguidores = to_int(followers_el.text)
        curtidas = to_int(likes_el.text)

        # Visualizações agregadas não aparecem no perfil; usamos proxy (curtidas) ou 0
        visualizacoes = curtidas

        # “Joias/Presentes” só ficam visíveis durante/live ou em abas específicas;
        # tentamos localizar um contador, caso contrário, None.
        joias = None
        try:
            gifts_el = driver.find_element(By.XPATH, "//span[contains(.,'Gifts') or contains(.,'Joias')]")
            joias = to_int(gifts_el.text)
        except Exception:
            joias = None

        return dict(seguidores=seguidores, curtidas=curtidas, visualizacoes=visualizacoes, joias=joias)
    except TimeoutException:
        st.error("TikTok: tempo limite excedido.")
        return None
    except Exception as e:
        st.error(f"TikTok: erro no scraping — {e}")
        return None
    finally:
        if driver:
            driver.quit()

def scrape_youtube(channel_url: str, timeout=25):
    """Coleta inscritos e (se possível) visualizações do canal público."""
    driver = None
    try:
        driver = get_driver()
        driver.set_page_load_timeout(timeout)
        st.info(f"YouTube: abrindo {channel_url}")
        driver.get(channel_url)
        wait = WebDriverWait(driver, timeout)

        # Inscritos
        subs_el = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//yt-formatted-string[contains(@id,'subscriber-count')]")
        ))
        inscritos = to_int(subs_el.text)

        # Visualizações (alguns canais exibem em /about)
        visualizacoes = None
        try:
            driver.get(channel_url.rstrip("/") + "/about")
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            # pega o primeiro texto que contém "views"
            els = driver.find_elements(By.XPATH, "//yt-formatted-string[contains(translate(., 'VIEWS', 'views'),'views')]")
            for el in els:
                visualizacoes = to_int(''.join([c for c in el.text if c.isdigit()]))
                if visualizacoes:
                    break
        except Exception:
            pass

        return dict(seguidores=inscritos, curtidas=None, visualizacoes=visualizacoes, joias=None)
    except TimeoutException:
        st.error("YouTube: tempo limite excedido.")
        return None
    except Exception as e:
        st.error(f"YouTube: erro no scraping — {e}")
        return None
    finally:
        if driver:
            driver.quit()

def scrape_kwai(username: str, timeout=25):
    """Coleta seguidores e curtidas de um perfil do Kwai (público)."""
    driver = None
    try:
        driver = get_driver()
        driver.set_page_load_timeout(timeout)
        url = f"https://www.kwai.com/@{username}"
        st.info(f"Kwai: abrindo {url}")
        driver.get(url)
        wait = WebDriverWait(driver, timeout)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Tentativas tolerantes (os textos variam por idioma)
        seguidores = None
        curtidas = None
        try:
            seguidores_el = driver.find_element(By.XPATH, "//*[contains(translate(.,'SEGUID','seguid'),'seguid')]")
            seguidores = to_int(''.join([c for c in seguidores_el.text if (c.isdigit() or c.lower() in 'km')]))
        except Exception:
            pass
        try:
            curtidas_el = driver.find_element(By.XPATH, "//*[contains(translate(.,'CURTI','curti'),'curti')]")
            curtidas = to_int(''.join([c for c in curtidas_el.text if (c.isdigit() or c.lower() in 'km')]))
        except Exception:
            pass

        return dict(seguidores=seguidos if (seguidos:=seguidores) is not None else None,
                    curtidas=curtidas, visualizacoes=None, joias=None)
    except TimeoutException:
        st.error("Kwai: tempo limite excedido.")
        return None
    except Exception as e:
        st.error(f"Kwai: erro no scraping — {e}")
        return None
    finally:
        if driver:
            driver.quit()

# -----------------------------------------------------------------------------
# PERSISTÊNCIA
# -----------------------------------------------------------------------------
def salvar_metricas(usuario_app, plataforma, influencer, met):
    cursor.execute("""
        INSERT INTO historico_metricas
        (usuario_app, plataforma, influencer, data, seguidores, curtidas, visualizacoes, joias)
        VALUES (?,?,?,?,?,?,?,?)
    """, (
        usuario_app, plataforma, influencer, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        met.get("seguidores"), met.get("curtidas"), met.get("visualizacoes"), met.get("joias")
    ))
    conn.commit()

def listar_influencers_usuario(usuario_app):
    df = pd.read_sql_query("""
        SELECT DISTINCT influencer, plataforma FROM historico_metricas
        WHERE usuario_app=?
        ORDER BY influencer
    """, conn, params=[usuario_app])
    return df

def exportar_excel(df, filename="relatorio.xlsx"):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        df.to_excel(tmp.name, index=False)
        tmp_path = tmp.name
    with open(tmp_path, "rb") as f:
        st.download_button("📥 Exportar Excel", f, file_name=filename,
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    os.unlink(tmp_path)

# -----------------------------------------------------------------------------
# UI — LOGIN / CADASTRO
# -----------------------------------------------------------------------------
if "usuario" not in st.session_state:
    st.session_state.usuario = None

menu = ["Login", "Cadastro"] if not st.session_state.usuario else ["Dashboard", "Sair"]
op = st.sidebar.selectbox("Menu", menu)

if op == "Login" and not st.session_state.usuario:
    st.title("Login")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if login_user(u, p):
            st.session_state.usuario = u
            if SAFE_RERUN: SAFE_RERUN()
        else:
            st.error("Usuário ou senha inválidos.")

elif op == "Cadastro" and not st.session_state.usuario:
    st.title("Cadastro")
    u = st.text_input("Novo usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Cadastrar"):
        if add_user(u, p):
            st.success("Usuário cadastrado! Faça login.")
        else:
            st.error("Usuário já existe.")

elif op == "Dashboard" and st.session_state.usuario:
    st.title(f"Bem-vindo(a), {st.session_state.usuario}")

    st.header("1) Coletar e salvar métricas")
    c1, c2, c3 = st.columns([1, 2, 2])
    with c1:
        plataforma = st.selectbox("Plataforma", ["tiktok", "youtube", "kwai"])
    with c2:
        influencer = st.text_input("Influencer/URL (TikTok/Kwai: usuário sem @ | YouTube: URL do canal)")
    with c3:
        st.caption("Dica: para YouTube, informe a URL do canal (ex.: https://www.youtube.com/@Canal)")

    if st.button("Buscar e salvar"):
        if not influencer.strip():
            st.warning("Informe o nome/URL.")
        else:
            if plataforma == "tiktok":
                met = scrape_tiktok(influencer.strip())
            elif plataforma == "youtube":
                met = scrape_youtube(influencer.strip())
            else:
                met = scrape_kwai(influencer.strip())

            if met:
                salvar_metricas(st.session_state.usuario, plataforma, influencer.strip(), met)
                st.success("Métricas salvas!")
                st.write(met)
            else:
                st.error("Não foi possível coletar as métricas.")

    st.header("2) Cadastro de presentes (catálogo)")
    with st.expander("Adicionar ao catálogo de presentes/joias"):
        nome_pres = st.text_input("Nome do presente")
        valor_moedas = st.number_input("Valor (moedas/diamantes)", min_value=1, step=1)
        if st.button("Salvar presente"):
            if nome_pres:
                try:
                    cursor.execute("INSERT INTO presentes_catalogo (nome, valor_moedas) VALUES (?,?)",
                                   (nome_pres.strip(), int(valor_moedas)))
                    conn.commit()
                    st.success("Presente cadastrado.")
                except sqlite3.IntegrityError:
                    st.error("Esse presente já está cadastrado.")
            else:
                st.warning("Informe um nome.")

    st.header("3) Registrar presentes recebidos")
    cat_df = pd.read_sql_query("SELECT id, nome, valor_moedas FROM presentes_catalogo ORDER BY nome", conn)
    if cat_df.empty:
        st.info("Cadastre ao menos um presente no catálogo acima.")
    else:
        inf_df = listar_influencers_usuario(st.session_state.usuario)
        if inf_df.empty:
            st.info("Sem histórico ainda. Busque e salve métricas na seção 1.")
        else:
            inf_opts = (inf_df["influencer"] + " (" + inf_df["plataforma"] + ")").tolist()
            col_r1, col_r2, col_r3, col_r4 = st.columns(4)
            with col_r1:
                inf_sel = st.selectbox("Influencer", inf_opts)
            with col_r2:
                presente_sel = st.selectbox("Presente", cat_df["nome"].tolist())
            with col_r3:
                qtd = st.number_input("Quantidade", min_value=1, step=1, value=1)
            with col_r4:
                data_reg = st.date_input("Data", datetime.now().date())

            if st.button("Registrar presentes recebidos"):
                influencer_nome = inf_sel.split(" (")[0]
                plataforma_nome = inf_sel.split(" (")[1].replace(")", "")
                pres_row = cat_df[cat_df["nome"] == presente_sel].iloc[0]
                cursor.execute("""
                    INSERT INTO presentes_recebidos (influencer, plataforma, data, presente_id, quantidade)
                    VALUES (?,?,?,?,?)
                """, (influencer_nome, plataforma_nome,
                      datetime.combine(data_reg, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S"),
                      int(pres_row["id"]), int(qtd)))
                conn.commit()
                st.success("Registro salvo.")

    st.header("4) Análise / Histórico")
    # filtros
    inf_df = listar_influencers_usuario(st.session_state.usuario)
    if inf_df.empty:
        st.info("Sem dados ainda.")
    else:
        inf_opts = (inf_df["influencer"] + " (" + inf_df["plataforma"] + ")").tolist()
        colf1, colf2, colf3 = st.columns(3)
        with colf1:
            inf_sel_mult = st.multiselect("Influencers", inf_opts, default=inf_opts[:1])
        with colf2:
            dt_ini = st.date_input("Início", datetime.now().date() - timedelta(days=30))
        with colf3:
            dt_fim = st.date_input("Fim", datetime.now().date())

        if st.button("Gerar análise"):
            inf_nomes = [s.split(" (")[0] for s in inf_sel_mult]
            plataformas = [s.split(" (")[1].replace(")", "") for s in inf_sel_mult]
            q = """
                SELECT * FROM historico_metricas
                WHERE usuario_app=?
                AND influencer IN ({})
                AND plataforma IN ({})
                AND datetime(data) BETWEEN ? AND ?
                ORDER BY datetime(data)
            """.format(",".join(["?"]*len(inf_nomes)), ",".join(["?"]*len(plataformas)))
            params = [st.session_state.usuario] + inf_nomes + plataformas + [
                f"{dt_ini} 00:00:00", f"{dt_fim} 23:59:59"
            ]
            df = pd.read_sql_query(q, conn, params=params)

            if df.empty:
                st.info("Sem registros para o período/seleção.")
            else:
                df["data"] = pd.to_datetime(df["data"])
                df["inf_plat"] = df["influencer"] + " (" + df["plataforma"] + ")"

                st.subheader("Evolução — Seguidores / Curtidas / Visualizações")
                base = df.melt(id_vars=["data","inf_plat"], value_vars=["seguidores","curtidas","visualizacoes"],
                               var_name="métrica", value_name="valor")
                base = base.dropna(subset=["valor"])
                fig = px.line(base, x="data", y="valor", color="inf_plat", line_dash="métrica",
                              title="Evolução de métricas")
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("Joias (presentes) — agregadas por mês")
                # joias salvas nas métricas e/ou via 'presentes_recebidos'
                # 4.1 — métricas diretas
                df_joias_m = df.dropna(subset=["joias"])[["data","inf_plat","joias"]].copy()
                df_joias_m["mes"] = df_joias_m["data"].dt.to_period("M").astype(str)

                # 4.2 — presentes_recebidos
                pr = pd.read_sql_query("""
                    SELECT pr.influencer, pr.plataforma, pr.data, pr.quantidade, pc.nome, pc.valor_moedas
                    FROM presentes_recebidos pr
                    JOIN presentes_catalogo pc ON pc.id = pr.presente_id
                    WHERE pr.influencer IN ({}) AND pr.plataforma IN ({})
                    AND datetime(pr.data) BETWEEN ? AND ?
                """.format(",".join(["?"]*len(inf_nomes)), ",".join(["?"]*len(plataformas))),
                    conn, params=inf_nomes+plataformas+[f"{dt_ini} 00:00:00", f"{dt_fim} 23:59:59"])

                if not pr.empty:
                    pr["data"] = pd.to_datetime(pr["data"])
                    pr["inf_plat"] = pr["influencer"] + " (" + pr["plataforma"] + ")"
                    pr["moedas_totais"] = pr["quantidade"] * pr["valor_moedas"]
                    pr["mes"] = pr["data"].dt.to_period("M").astype(str)
                    joias_recebidas_mes = pr.groupby(["inf_plat","mes"], as_index=False)["moedas_totais"].sum()
                else:
                    joias_recebidas_mes = pd.DataFrame(columns=["inf_plat","mes","moedas_totais"])

                # Unifica (métricas diretas + recibos em moedas)
                if not df_joias_m.empty:
                    j1 = df_joias_m.groupby(["inf_plat","mes"], as_index=False)["joias"].max()
                    j1.rename(columns={"joias":"moedas_totais"}, inplace=True)
                    joias_mes = pd.concat([j1, joias_recebidas_mes], ignore_index=True)
                else:
                    joias_mes = joias_recebidas_mes.copy()

                if not joias_mes.empty:
                    figj = px.bar(joias_mes, x="mes", y="moedas_totais", color="inf_plat",
                                  barmode="group", title="Joias / Presentes (moedas) por mês")
                    st.plotly_chart(figj, use_container_width=True)
                else:
                    st.info("Sem dados de joias nesse período.")

                st.subheader("Tabela detalhada")
                st.dataframe(df, use_container_width=True)
                exportar_excel(df, filename=f"relatorio_{dt_ini}_{dt_fim}.xlsx")

elif op == "Sair":
    st.session_state.usuario = None
    if SAFE_RERUN: SAFE_RERUN()
