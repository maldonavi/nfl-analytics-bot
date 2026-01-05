import streamlit as st
import pandas as pd
import sqlite3
import spacy
import subprocess
import sys
import re

def load_nlu_model():
    model_name = "es_core_news_sm"
    try:
        # Intenta cargar el modelo si ya está instalado
        return spacy.load(model_name)
    except OSError:
        # Si falla, fuerza la descarga directa usando el ejecutable de Python del servidor
        subprocess.check_call([sys.executable, "-m", "spacy", "download", model_name])
        return spacy.load(model_name)
nlp = load_nlu_model()

# Configuración de la página (Profesionalismo)
st.set_page_config(page_title="Bot de analisis NFL", page_icon="🏈", layout="wide")

st.markdown("""
    <style>
    /* Cambiar el color de fondo de la barra lateral */
    [data-testid="stSidebar"] {
        background-color: #013369;
        color: white;
    }
    /* Estilizar los títulos de la barra lateral */
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2 {
        color: #ffffff;
    }
    /* Tarjetas de resultados con bordes redondeados */
    .result-card {
        background-color: white;
        padding: 20px;
        border-left: 5px solid #D50A0A; /* Rojo NFL */
        border-radius: 10px;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CARGA DE MODELOS Y FUNCIONES (Tus módulos anteriores integrados) ---
@st.cache_resource
def load_nlp():
    return spacy.load("es_core_news_sm")

nlp = load_nlp()

def nfl_entity_extractor(text):
    doc = nlp(text.lower())
    entities = {"equipo": [], "jugada": None, "situacion": None, "anio": None,"intencion": "tactica",}
    
    # 1. DICCIONARIO UNIVERSAL DE LA NFL (32 EQUIPOS)
    # Mapea variaciones de lenguaje natural a la abreviatura de la BD
    equipos_map = {
        # AFC East
        "bills": "BUF", "buffalo": "BUF", "buf": "BUF",
        "dolphins": "MIA", "miami": "MIA", "mia": "MIA",
        "patriots": "NE", "patriotas": "NE", "ne": "NE", "new england": "NE",
        "jets": "NYJ", "nyj": "NYJ",
        # AFC North
        "ravens": "BAL", "baltimore": "BAL", "bal": "BAL",
        "bengals": "CIN", "cincinnati": "CIN", "cin": "CIN",
        "browns": "CLE", "cleveland": "CLE", "cle": "CLE",
        "steelers": "PIT", "pittsburgh": "PIT", "pit": "PIT",
        # AFC South
        "texans": "HOU", "houston": "HOU", "hou": "HOU",
        "colts": "IND", "indianapolis": "IND", "ind": "IND",
        "jaguars": "JAX", "jacksonville": "JAX", "jax": "JAX",
        "titans": "TEN", "tennessee": "TEN", "ten": "TEN",
        # AFC West
        "chiefs": "KC", "kansas": "KC", "kc": "KC",
        "broncos": "DEN", "denver": "DEN", "den": "DEN",
        "raiders": "LV", "vegas": "LV", "lv": "LV",
        "chargers": "LAC", "lac": "LAC",
        # NFC East
        "eagles": "PHI", "philadelphia": "PHI", "phi": "PHI", "águilas": "PHI",
        "cowboys": "DAL", "dallas": "DAL", "dal": "DAL", "vaqueros": "DAL",
        "giants": "NYG", "gigantes": "NYG", "nyg": "NYG",
        "commanders": "WAS", "washington": "WAS", "was": "WAS",
        # NFC North
        "lions": "DET", "detroit": "DET", "det": "DET",
        "vikings": "MIN", "minnesota": "MIN", "min": "MIN",
        "packers": "GB", "green bay": "GB", "gb": "GB",
        "bears": "CHI", "chicago": "CHI", "chi": "CHI",
        # NFC South
        "falcons": "ATL", "atlanta": "ATL", "atl": "ATL",
        "panthers": "CAR", "carolina": "CAR", "car": "CAR",
        "saints": "NO", "orleans": "NO", "no": "NO",
        "buccaneers": "TB", "tampa": "TB", "tb": "TB", "bucs": "TB",
        # NFC West
        "49ers": "SF", "niners": "SF", "francisco": "SF", "sf": "SF",
        "seahawks": "SEA", "seattle": "SEA", "sea": "SEA",
        "cardinals": "ARI", "arizona": "ARI", "ari": "ARI",
        "rams": "LAR", "los angeles": "LAR", "lar": "LAR"
    }
    jugadas = {"pase": "pass", "pass": "pass", "carrera": "run", "run": "run"}
    mapping_downs = {"1er": "1", "1o": "1", "2do": "2", "2o": "2", "3er": "3", "3o": "3", "4to": "4", "4o": "4"}
    palabras_historia = ["ganó", "perdió", "marcador", "resultado", "campeón", "vs"]
    if any(p in text.lower() for p in palabras_historia):
        entities["intencion"] = "historica"

    # 3. Lógica de Extracción mejorada
    anio_encontrado = re.findall(r'202[1-5]', text)
    if anio_encontrado:
        entities["anio"] = int(anio_encontrado[0])

    text_clean = text.lower()
    
    # Buscar equipos (incluyendo nombres compuestos como "New Orleans")
    for nombre, abreviatura in equipos_map.items():
        if nombre in text_clean:
            if abreviatura not in entities["equipo"]:
                entities["equipo"].append(abreviatura)
    entities["solo_local"] = any(word in text_clean for word in ["en casa", "en " + entities["equipo"][0].lower() if entities["equipo"] else ""])

    if any(p in text_clean for p in ["ganó", "resultado", "vs", "enfrentamiento"]):
        entities ["intencion"] = "historica"
            
    for token in doc:
        # Identificar Jugada
        if token.text in jugadas:
            entities["jugada"] = jugadas[token.text]
        # Identificar Situación
        for key, value in mapping_downs.items():
            if key in token.text:
                entities["situacion"] = value

    if "zona roja" in text_clean or "red zone" in text_clean:
        entities["situacion"] = "zona_roja"
        
    return entities
def execute_historical_query(entities):
    try:
        conn = sqlite3.connect('nfl_data.db')
        equipos = entities["equipo"]
        if len(equipos) == 2:
            # CASO: Enfrentamiento directo (PIT vs BAL)
            query = """
                SELECT season, week, gameday, home_team, away_team, home_score, away_score 
                FROM games 
                WHERE ((home_team = ? AND away_team = ?) OR (home_team = ? AND away_team = ?))
                AND home_score IS NOT NULL
                ORDER BY gameday DESC LIMIT 5
            """
            params = [equipos[0], equipos[1], equipos[1], equipos[0]]
        else:
            # CASO: Un solo equipo (Como lo tenías antes)
            query = """
                SELECT season, week, gameday, home_team, away_team, home_score, away_score 
                FROM games 
                WHERE (home_team = ? OR away_team = ?)
                AND home_score IS NOT NULL
                ORDER BY gameday DESC LIMIT 5
            """
            params = [equipos[0], equipos[0]]
            
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        return pd.DataFrame()

def execute_query_safe(entities):
    try:
        conn = sqlite3.connect('nfl_data.db')
        # Añadimos limpieza de nulos directamente en el SQL
        if entities["anio"]:
            query = """
                SELECT p.posteam, p.down, p.play_type, p.yards_gained, p.touchdown, p.epa 
                FROM plays p
                JOIN games g ON p.game_id = g.game_id
                WHERE p.epa IS NOT NULL AND g.season = ?
            """
            params = [entities["anio"]]
        else:
            query = "SELECT posteam, down, play_type, yards_gained, touchdown, epa FROM plays WHERE epa IS NOT NULL"
            params = []
        
        if entities["equipo"]:
            query += " AND posteam = ?"
            params.append(entities["equipo"][0])
        
        if entities["jugada"]:
            query += " AND play_type = ?"
            params.append(entities["jugada"])
            
        if entities["situacion"]:
            if entities["situacion"] == "zona_roja":
                query += " AND yardline_100 <= 20"
            else:
                query += " AND down = ?"
                params.append(int(entities["situacion"]))

        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        st.error(f"⚠️ Error técnico en la base de datos: {e}")
        return pd.DataFrame()
# --- FUNCIÓN DE REFERENCIA GLOBAL (BENCHMARK) ---
@st.cache_data
def get_league_baseline():
    """
    Calcula el promedio de eficiencia (EPA) de toda la liga 
    para usarlo como punto de comparación.
    """
    try:
        conn = sqlite3.connect('nfl_data.db')
        # Obtenemos el promedio de los 125,403 registros cargados en la Fase 1
        query = "SELECT AVG(epa) as avg_epa FROM plays WHERE epa IS NOT NULL"
        baseline_df = pd.read_sql_query(query, conn)
        conn.close()
        
        if not baseline_df.empty:
            return baseline_df['avg_epa'].iloc[0]
        return 0.0 # Valor por defecto si la tabla está vacía
    except Exception as e:
        st.error(f"Error al calcular el benchmark de la liga: {e}")
        return 0.0

# --- INTERFAZ GRÁFICA ---
st.title("Sistema Interactivo de Descubrimiento de Conocimiento para Analítica de la NFL")
st.markdown("""
    Este sistema utiliza **Minería de Reglas de Asociación** y **NLP** para descubrir patrones 
    estratégicos en la NFL (Temporadas 2021-2023).
""")

# Barra lateral con información técnica (Para el jurado)
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/en/thumb/a/a2/National_Football_League_logo.svg/1200px-National_Football_League_logo.svg.png", width=100)
    st.title("Lista de equipos")
    with st.expander("🏈 Conferencia Americana (AFC)"):
        cols = st.columns(2)
        afc_teams = ["NE", "BUF", "MIA", "NYJ", "PIT", "BAL", "CLE", "CIN", "HOU", "IND", "TEN", "JAX", "KC", "LAC", "DEN", "LV"]
        for i, team in enumerate(afc_teams):
            with cols[i % 2]:
                st.image(f"https://a.espncdn.com/i/teamlogos/nfl/500/{team.lower()}.png", width=40)
                st.caption(team)

    with st.expander("🏈 Conferencia Nacional (NFC)"):
        cols = st.columns(2)
        nfc_teams = ["PHI", "DAL", "NYG", "WAS", "GNB", "DET", "CHI", "MIN", "SF", "SEA", "LAR", "ARI", "CAR", "TAM", "NO", "ATL"]
        for i, team in enumerate(nfc_teams):
            with cols[i % 2]:
                st.image(f"https://a.espncdn.com/i/teamlogos/nfl/500/{team.lower()}.png", width=40)
                st.caption(team)

# Chat Interface
pregunta = st.text_input("Haz una pregunta:", placeholder="Ej: ¿Cómo le va a KC en el 3er down con el pase?")

if pregunta:
    with st.spinner('Procesando tu consulta...'):
        entidades = nfl_entity_extractor(pregunta)
        
        # --- NIVEL 1: Despacho de Intención Histórica ---
        # Requiere intención explícita ("ganó", "resultado") Y un equipo identificado.
        if entidades["intencion"] == "historica" and entidades["equipo"]:
            st.info(f"📜 Consultando archivos históricos para {entidades['equipo']}...")
            df_hist = execute_historical_query(entidades)
            
            if not df_hist.empty:
                st.subheader(f"🏟️ Últimos resultados de {entidades['equipo']}")
                for _, row in df_hist.iterrows():
                # Validamos si los puntajes son números válidos antes de convertirlos
                    h_score = int(row['home_score']) if pd.notna(row['home_score']) else "TBD"
                    a_score = int(row['away_score']) if pd.notna(row['away_score']) else "TBD"
        
                # Formato limpio: Semana X (Año): Local vs Visitante
                    st.write(f"**Semana {row['week']} ({row['season']})**: {row['home_team']} **{h_score}** - **{a_score}** {row['away_team']}")
                
        # --- NIVEL 2: Despacho de Intención Táctica ---
        # Si no es histórico, verificamos si tiene sentido táctico.
        # ¿Tenemos al menos UN componente táctico claro?
        elif any([entidades["equipo"], entidades["jugada"], entidades["situacion"]]):
            st.info("🧠 Iniciando análisis táctico y minería de datos...")
            df_res = execute_query_safe(entidades)
            
            if not df_res.empty:
                st.success("¡Análisis completado!")
                
                # --- KPI CARDS ---
                col1, col2, col3 = st.columns(3)
                epa_prom = df_res['epa'].mean()
                pct_exito = (df_res['epa'] > 0).mean() * 100
                total_tds = df_res['touchdown'].sum()

                with col1: st.metric("Eficiencia (EPA)", f"{epa_prom:.3f}")
                with col2: st.metric("Tasa de Éxito", f"{pct_exito:.1f}%")
                with col3: st.metric("Touchdowns", int(total_tds))

                # --- GRÁFICOS Y BENCHMARK ---
                st.divider()
                
                # 1. Gráfico de Distribución de Yardas
                st.subheader("📊 Distribución de Yardaje")
                st.area_chart(df_res['yards_gained'], color="#D50A0A")

                # 2. Benchmark vs Liga
                st.subheader("📈 Comparativa vs. Promedio de la Liga")
                league_avg_epa = get_league_baseline()
                epa_equipo = df_res['epa'].mean()
                comparativa_data = pd.DataFrame({
                    'Categoría': ['Selección Actual', 'Promedio NFL'],
                    'EPA Promedio': [epa_equipo, league_avg_epa]
                })

                # SOLUCIÓN AL ERROR: Usamos color='Categoría' para que asigne colores automáticamente
                st.bar_chart(
                    data=comparativa_data, 
                    x='Categoría', 
                    y='EPA Promedio', 
                    color='Categoría' # Esto soluciona el ColorLengthError
                )

                # Interpretación estadística (NLG)
                # Usamos LaTeX para la fórmula de diferencia si lo incluyes en tu reporte
                # $\Delta EPA = EPA_{equipo} - EPA_{league}$
                if epa_equipo > league_avg_epa:
                    st.info(f"💡 **Hallazgo:** El rendimiento es {(epa_equipo - league_avg_epa):.3f} puntos superior a la media de la liga.")
                else:
                    st.warning(f"💡 **Nota:** El rendimiento está {(league_avg_epa - epa_equipo):.3f} puntos por debajo de la media.")
                                    
            else:
                st.warning("No encontré jugadas que coincidan exactamente con esa combinación de criterios.")

        # --- NIVEL 3: Manejo de Ambigüedad (Fallback) ---
        else:
            st.error("🤔 No estoy seguro de qué me preguntas.")
            st.markdown("""
                **Intenta ser más específico. Por ejemplo:**
                - *Táctico:* "¿Cómo le va a los **Cowboys** con el **pase** en **zona roja**?"
                - *Histórico:* "¿Quién **ganó** el último juego de los **Chiefs**?"
            """)
