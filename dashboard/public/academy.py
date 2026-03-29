"""
academy.py — Academia Pro: conocimiento avanzado de crypto y memecoins.

Solo accesible para usuarios Pro/Admin. Contenido educativo avanzado
organizado en tabs: blockchains, narrativas, analisis de tokens,
gestion de riesgo y herramientas del trader.

Todo el contenido esta en espanol y orientado a traders de memecoins
que ya tienen los conceptos basicos.
"""

import streamlit as st


def render():
    """Academia Pro — Conocimiento avanzado de crypto y memecoins."""

    # --- Gate Pro/Admin ---
    try:
        from dashboard.paywall import check_feature_access, show_upgrade_prompt
        if not check_feature_access("academy_pro"):
            show_upgrade_prompt("Academia Pro")
            return
    except ImportError:
        pass  # Sin paywall en desarrollo

    st.header(":material/school: Academia Pro")
    st.caption(
        "Contenido avanzado para traders de memecoins. "
        "Aprende a analizar tokens, gestionar riesgo y usar herramientas profesionales."
    )

    # --- Disclaimer ---
    st.warning(
        "**Aviso legal:** Este contenido es educativo. No constituye asesoramiento "
        "financiero, de inversion ni legal. Las criptomonedas son activos altamente "
        "especulativos. Puedes perder la totalidad de tu inversion. DYOR."
    )

    # --- Tabs principales ---
    tab_chains, tab_narrativas, tab_analisis, tab_riesgo, tab_herramientas = st.tabs([
        "Blockchains",
        "Narrativas",
        "Analisis de Tokens",
        "Gestion de Riesgo",
        "Herramientas",
    ])

    # ==================================================================
    # TAB 1: BLOCKCHAINS Y ECOSISTEMAS
    # ==================================================================
    with tab_chains:
        st.subheader("Blockchains y ecosistemas")
        st.info(
            "**Por que importa esto?** Cada blockchain tiene sus propias reglas, "
            "costes y ecosistema. Entender donde operas es el primer paso para "
            "tomar mejores decisiones."
        )

        # --- Solana ---
        with st.expander("Solana — Velocidad y bajo coste", expanded=True):
            st.markdown("""
**Solana** es una blockchain de capa 1 (L1) disenada para ser rapida y barata.

**Caracteristicas clave:**
- **Velocidad:** ~400ms por bloque, transacciones casi instantaneas
- **Coste:** Gas fees de ~$0.001 por transaccion (casi gratis)
- **Ecosistema DeFi:** Jupiter (DEX agregador), Raydium (AMM), Marinade (staking liquido)
- **Memecoins:** Es la blockchain mas activa para memecoins nuevos. Pump.fun genero miles de tokens diarios

**Para el trader de memecoins:**
- La velocidad y bajo coste la hacen ideal para trading activo
- Phantom es la wallet estandar
- Jupiter es el DEX principal (agrega liquidez de multiples fuentes)
- Mayor volumen de memecoins nuevos = mas oportunidades, pero tambien mas scams
            """)

        # --- Ethereum ---
        with st.expander("Ethereum — Smart contracts y ERC-20"):
            st.markdown("""
**Ethereum** es la primera blockchain con smart contracts. La mayor parte de DeFi se construyo aqui.

**Caracteristicas clave:**
- **Smart contracts:** Programas autonomos que ejecutan logica sin intermediarios
- **ERC-20:** Estandar para crear tokens (la mayoria de altcoins y memecoins de Ethereum siguen este estandar)
- **Gas fees:** Históricamente altas ($5-$50+ por transaccion), lo que frena el trading de memecoins pequenos
- **Seguridad:** La blockchain mas probada y segura despues de Bitcoin

**Para el trader de memecoins:**
- Gas fees altas = solo viable para posiciones de cierto tamano
- MetaMask es la wallet estandar
- Uniswap es el DEX principal
- PEPE, SHIB, FLOKI — los memecoins clasicos estan aqui
            """)

        # --- Base ---
        with st.expander("Base — L2 de Coinbase"):
            st.markdown("""
**Base** es una Layer 2 (L2) construida sobre Ethereum por Coinbase.

**Caracteristicas clave:**
- **L2 (Layer 2):** Usa la seguridad de Ethereum pero procesa transacciones mas rapido y barato
- **Bajo coste:** Gas fees de centimos, no dolares
- **Respaldo de Coinbase:** Credibilidad institucional, base de usuarios grande
- **Crecimiento:** Ecosistema en rapida expansion desde 2024

**Para el trader de memecoins:**
- Bajo coste como Solana pero con la seguridad de Ethereum
- MetaMask funciona (anadir red Base)
- Aerodrome es el DEX principal
- Ecosistema mas joven = tokens con menos historial
            """)

        # --- Tabla comparativa ---
        st.markdown("---")
        st.markdown("#### Comparativa rapida")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown("**Metrica**")
            st.markdown("TPS (trans/seg)")
            st.markdown("Gas fee tipico")
            st.markdown("Wallet principal")
            st.markdown("DEX principal")
            st.markdown("Memecoins activos")
        with col2:
            st.markdown("**Solana**")
            st.markdown("~4,000")
            st.markdown("~$0.001")
            st.markdown("Phantom")
            st.markdown("Jupiter")
            st.markdown("Miles (diarios)")
        with col3:
            st.markdown("**Ethereum**")
            st.markdown("~30")
            st.markdown("$5-50+")
            st.markdown("MetaMask")
            st.markdown("Uniswap")
            st.markdown("Cientos")
        with col4:
            st.markdown("**Base**")
            st.markdown("~100+")
            st.markdown("~$0.01")
            st.markdown("MetaMask")
            st.markdown("Aerodrome")
            st.markdown("Creciendo")

    # ==================================================================
    # TAB 2: NARRATIVAS
    # ==================================================================
    with tab_narrativas:
        st.subheader("Narrativas de mercado")
        st.info(
            "**Que es una narrativa?** Una tendencia o tema que mueve capital en crypto. "
            "Los tokens que se alinean con la narrativa dominante tienden a subir mas rapido."
        )

        # --- Concepto de narrativa ---
        with st.expander("Como funcionan las narrativas", expanded=True):
            st.markdown("""
En crypto, el dinero sigue **historias**. Cuando suficientes personas creen en una narrativa,
compran tokens relacionados, lo que sube el precio, lo que atrae mas personas. Es un ciclo
que se retroalimenta... hasta que se rompe.

**Ejemplo real:** En 2023, la narrativa de "AI tokens" hizo que cualquier token con "AI" en el
nombre subiera 5-50x, independientemente de si tenia tecnologia real de IA o no.

**La leccion:** No importa si la narrativa es "correcta" — importa si suficiente gente la cree
durante suficiente tiempo para que puedas entrar y salir con beneficios.
            """)

        # --- Narrativas actuales ---
        with st.expander("Narrativas relevantes"):
            st.markdown("""
**AI Tokens** — Tokens asociados a inteligencia artificial. Desde agentes autonomos hasta
infraestructura de computacion descentralizada.

**RWA (Real World Assets)** — Tokenizacion de activos del mundo real: inmuebles, bonos,
materias primas. Narrativa mas "institucional".

**Memecoins** — La narrativa eterna. Nuevas olas de memecoins emergen con cada ciclo.
En 2024-2025: memecoins de personajes politicos, mascotas, y cultura viral.

**DePIN (Decentralized Physical Infrastructure)** — Redes descentralizadas de infraestructura
fisica: WiFi, almacenamiento, sensores, energia.

**Gaming/SocialFi** — Juegos on-chain y redes sociales descentralizadas. Ciclos de hype
recurrentes.
            """)

        # --- Detectar narrativas ---
        with st.expander("Como detectar narrativas emergentes"):
            st.markdown("""
**Senales tempranas de una narrativa:**

1. **Crypto Twitter (X):** Los KOLs (Key Opinion Leaders) empiezan a hablar de un tema nuevo.
   Si ves 3-5 cuentas influyentes hablando de lo mismo en 24h, presta atencion.

2. **Volumen en DEXs:** Tokens de una categoria concreta empiezan a tener volumen inusual.
   DexScreener y GeckoTerminal muestran trending tokens.

3. **Noticias macro:** Regulaciones, adopcion institucional, eventos tecnologicos.
   Ejemplo: el lanzamiento de ChatGPT disparo la narrativa de AI tokens.

4. **Nuevos protocolos:** Si aparece una nueva plataforma que facilita crear tokens de un tipo
   (como Pump.fun para memecoins en Solana), espera una explosion de oferta.

**Regla practica:** Si crees que has "descubierto" una narrativa viendo un tweet viral,
probablemente ya vas tarde. Las mejores oportunidades estan ANTES del hype masivo.
            """)

        # --- Ciclo de vida ---
        with st.expander("Ciclo de vida de una narrativa"):
            st.markdown("""
Toda narrativa sigue un patron predecible:

**Fase 1 — Early (Descubrimiento)**
- Solo los insiders y early adopters hablan de ello
- Los tokens estan baratos, baja liquidez
- Riesgo alto, recompensa potencial maxima

**Fase 2 — Growth (Adopcion)**
- Los KOLs de crypto empiezan a hablar de ello
- Los tokens suben 5-20x
- Es el momento mas rentable con riesgo "razonable"

**Fase 3 — Mainstream (Masa critica)**
- Titulares en medios generales, tu primo te pregunta
- Los tokens ya han subido 50-100x desde el inicio
- "Si todo el mundo habla de ello, ya es tarde para entrar"

**Fase 4 — Saturacion (Declive)**
- Demasiados tokens de baja calidad copiando la narrativa
- Los insiders empiezan a vender
- El precio colapsa, la narrativa "muere" (hasta el proximo ciclo)
            """)

            st.warning(
                "**Consejo:** Intenta estar en Fase 1-2. Si llegas en Fase 3, "
                "tu riesgo/recompensa es mucho peor. En Fase 4, no compres."
            )

    # ==================================================================
    # TAB 3: ANALISIS DE TOKENS
    # ==================================================================
    with tab_analisis:
        st.subheader("Analisis de tokens")
        st.info(
            "**Antes de comprar cualquier token**, dedica 5-10 minutos a analizarlo. "
            "Estos son los aspectos que miran los traders profesionales."
        )

        # --- Tokenomics ---
        with st.expander("Tokenomics: La economia del token", expanded=True):
            st.markdown("""
**Tokenomics** = las reglas economicas que gobiernan un token. Es lo primero que debes revisar.

**Supply (oferta):**
- **Total Supply:** Cuantos tokens existiran en total
- **Circulating Supply:** Cuantos estan en circulacion ahora
- Si hay gran diferencia, significa que saldran muchos tokens nuevos (dilucion = presion de venta)

**Distribucion:**
- Como se repartieron los tokens al lanzamiento?
- Si el equipo tiene >20% del supply, pueden vender y hundir el precio
- Busca distribucion amplia entre muchos holders

**Vesting (bloqueo temporal):**
- Los tokens del equipo e inversores suelen tener un periodo de bloqueo
- Cuando se desbloquean (unlock), suele haber presion de venta
- Consulta el calendario de unlocks antes de comprar

**Inflacion vs Deflacion:**
- Algunos tokens tienen mecanismos de burn (queman tokens, reducen supply)
- Otros tienen emision continua (mas tokens = dilucion)
- Para memecoins, la mayoria tiene supply fijo (ni inflacion ni deflacion)
            """)

        # --- On-chain analysis ---
        with st.expander("On-chain analysis: Que miran los profesionales"):
            st.markdown("""
Todo lo que pasa en blockchain es publico. Los profesionales analizan estos datos:

**Actividad de wallets:**
- Numero de holders unicos y tendencia (creciendo o decreciendo?)
- Transacciones diarias (actividad real o bots?)
- Nuevos vs antiguos holders (los nuevos estan comprando o los antiguos vendiendo?)

**Flujos de liquidez:**
- La liquidez esta creciendo o decreciendo?
- Hay grandes retiradas de liquidez recientes? (senal de alerta)
- Ratio liquidez / market cap (cuanto mas alto, mejor)

**Actividad de smart contracts:**
- El contrato tiene funciones peligrosas? (mint infinito, blacklist, honeypot)
- Esta verificado y auditable?
- Tiene ownership renounced? (el creador ya no puede modificarlo)
            """)

        # --- Smart money tracking ---
        with st.expander("Smart money tracking: Seguir wallets rentables"):
            st.markdown("""
**Smart money** = wallets que consistentemente generan beneficios. Si descubres una,
puedes monitorear que compra.

**Como encontrar smart money:**
1. En DexScreener, mira los "Top Traders" de un token que hizo 10x+
2. Identifica wallets que compraron temprano y vendieron en maximo
3. Sigue esas wallets para ver que compran despues

**Herramientas:**
- **Arkham Intelligence:** Etiqueta wallets conocidas (fondos, exchanges, insiders)
- **Nansen:** Analytics on-chain premium (smart money labels)
- **DEXScreener Top Traders:** Gratis, muestra las wallets mas rentables por token

**Advertencia:** No copies ciegamente. Las smart money wallets tambien pierden.
Usa esta informacion como UNA senal mas, no como la unica.
            """)

        # --- Social signals ---
        with st.expander("Social signals: Actividad en redes"):
            st.markdown("""
Las redes sociales mueven el precio de memecoins mas que cualquier fundamental.

**Twitter/X:**
- Volumen de menciones del token (creciendo = interes)
- Calidad de las cuentas que mencionan (KOLs con reputacion vs bots)
- Engagement real vs comprado (comentarios con contenido vs emojis de bots)

**Telegram:**
- Tamano del grupo y crecimiento
- Actividad real de la comunidad (conversaciones vs spam)
- Presencia del equipo respondiendo preguntas

**Discord:**
- Similar a Telegram pero permite mas organizacion
- Busca canales activos de desarrollo y updates

**Herramienta clave:** LunarCrush mide el "social engagement" de tokens.
Un aumento subito de social signals ANTES de un pump de precio es una senal alcista.
            """)

    # ==================================================================
    # TAB 4: GESTION DE RIESGO AVANZADA
    # ==================================================================
    with tab_riesgo:
        st.subheader("Gestion de riesgo avanzada")
        st.info(
            "**La gestion de riesgo es lo que separa a los traders que sobreviven "
            "de los que pierden todo.** No es la parte mas emocionante, pero es la mas importante."
        )

        # --- Position sizing ---
        with st.expander("Position sizing: Cuanto invertir en cada token", expanded=True):
            st.markdown("""
**La regla de oro:** Nunca pongas mas del 1-5% de tu capital total de memecoins en un solo token.

**Kelly Criterion simplificado:**

El Kelly Criterion es una formula matematica que calcula el tamano optimo de una apuesta
basandose en tu probabilidad de ganar y el ratio de pago.

**Version simplificada para memecoins:**
- Si crees que un token tiene un 10% de probabilidad de hacer 10x:
  - Kelly = (0.10 x 10 - 0.90) / 10 = 0.01 = **1% del portfolio**
- Si crees que tiene un 5% de probabilidad de hacer 50x:
  - Kelly = (0.05 x 50 - 0.95) / 50 = 0.031 = **3.1% del portfolio**

**En la practica:** La mayoria de traders profesionales de memecoins usan "fraccional Kelly"
(la mitad o un cuarto del Kelly calculado) para ser mas conservadores.

**Regla practica:** Si no sabes calcular, usa el 1-2% por token. Con 50-100 EUR por posicion
en un portfolio de 5000 EUR.
            """)

        # --- Stop-loss ---
        with st.expander("Stop-loss en crypto"):
            st.markdown("""
**El problema:** En memecoins con baja liquidez, los stop-loss automaticos pueden ser
disparados por wicks (mechas) temporales y venderte a un precio terrible.

**Stop-loss mental vs On-chain:**

| Tipo | Como funciona | Ventaja | Desventaja |
|------|--------------|---------|------------|
| Mental | Decides un precio y vendes tu manualmente | No te sacan con wicks | Requiere disciplina |
| On-chain (limit order) | Colocas una orden en el DEX | Automatico | Puede ejecutarse en mal momento |

**Recomendacion para memecoins:**
- Usa stop-loss **mental** con alerta (ej: alerta de precio en DexScreener)
- Si un token baja un 50% desde tu compra, vende y acepta la perdida
- NUNCA "promedies a la baja" en un memecoin (comprar mas cuando baja)
- Mejor perder un 50% que un 100%
            """)

        # --- Diversificacion ---
        with st.expander("Diversificacion en memecoins"):
            st.markdown("""
**La estrategia de "basket" (cesta):**

En lugar de buscar "el" memecoin ganador, construye una cartera de 10-20 posiciones pequenas.

**La matematica a tu favor:**
- 20 posiciones de 50 EUR = 1000 EUR total
- Si 18 van a cero (pierdes 900 EUR)
- Pero 1 hace 20x (ganaste 1000 EUR)
- Y 1 hace 5x (ganaste 250 EUR)
- **Resultado: 1250 EUR con 1000 EUR invertidos = +25% incluso con 90% de perdedores**

**Diversifica tambien por blockchain:**
- No pongas todo en Solana o todo en Ethereum
- Cada blockchain tiene su propio ciclo de hype

**Y por narrativa:**
- Mezcla memecoins de diferentes narrativas (AI, animales, personajes, cultura)
- Cuando una narrativa muere, otra puede estar naciendo
            """)

        # --- DCA vs Lump Sum ---
        with st.expander("DCA vs Lump Sum"):
            st.markdown("""
**DCA (Dollar Cost Averaging):** Comprar cantidades fijas en intervalos regulares
(ej: 100 EUR cada semana).

**Lump Sum:** Comprar todo de una vez.

**En memecoins:**

| Estrategia | Cuando usarla |
|-----------|--------------|
| DCA | Cuando quieres exposicion a un memecoin que crees que tiene recorrido a medio plazo |
| Lump Sum | Cuando ves una oportunidad clara y quieres maxima exposicion inmediata |

**Realidad:** En memecoins, la mayoria de la accion ocurre en horas o dias, no semanas.
DCA tiene mas sentido para crypto "serias" (BTC, ETH, SOL). Para memecoins, el timing
es mas importante que el DCA.
            """)

        # --- Tomar profits ---
        with st.expander("Cuando tomar profits: la regla del 2x/5x/10x"):
            st.markdown("""
**El mayor error de los traders de memecoins:** No vender nunca y ver como las ganancias
se evaporan.

**La regla escalonada:**

| Multiplicador | Accion | Por que |
|--------------|--------|---------|
| **2x** (doblas) | Vende el 50% (recuperas tu inversion inicial) | Ya estas jugando "con dinero gratis" |
| **5x** | Vende otro 25% del restante | Aseguras un beneficio significativo |
| **10x** | Vende otro 25% | Beneficio excelente asegurado |
| **Moonbag** | Deja el ultimo 25% | Si hace 100x, aun tienes exposicion |

**Ejemplo con 100 EUR:**
1. A 2x (200 EUR): vendes 100 EUR → recuperas inversion. Queda: 100 EUR en tokens
2. A 5x (250 EUR en tokens): vendes 62.50 EUR → quedan 187.50 EUR en tokens
3. A 10x (375 EUR en tokens): vendes 93.75 EUR → quedan 281.25 EUR de "moonbag"

**Total retirado: 256.25 EUR** (ya ganaste 156.25 EUR)
**Moonbag: 281.25 EUR** que puede llegar a 0... o a 100x
            """)

            st.success(
                "**La clave:** Tomar profits parciales elimina la presion emocional. "
                "Si el token sube, aun tienes exposicion. Si baja, ya aseguraste ganancias."
            )

    # ==================================================================
    # TAB 5: HERRAMIENTAS DEL TRADER
    # ==================================================================
    with tab_herramientas:
        st.subheader("Herramientas del trader")
        st.info(
            "**Las herramientas adecuadas marcan la diferencia.** Aqui tienes las que usan "
            "los traders profesionales de memecoins a diario."
        )

        # --- DexScreener ---
        with st.expander("DexScreener — Graficos y trending", expanded=True):
            st.markdown("""
**URL:** [dexscreener.com](https://dexscreener.com)

**Que es:** Agregador de datos de DEXs en multiples blockchains. Es la herramienta numero 1
para traders de memecoins.

**Como usarlo:**
1. **Trending:** La pagina principal muestra tokens con mayor volumen/variacion
2. **Buscar token:** Pega la direccion del contrato para ver precio, liquidez, holders
3. **Graficos:** Velas japonesas con indicadores basicos (MA, volumen)
4. **Top Traders:** Ve las wallets mas rentables de cada token
5. **Filtros:** Filtra por blockchain, edad del token, liquidez minima

**Senales a buscar en DexScreener:**
- Liquidez creciente (LP crece, no decrece)
- Volumen alto relativo al market cap
- Numero de compradores > vendedores
- Token con mas de 24h de vida y aun creciendo
            """)

        # --- BubbleMaps ---
        with st.expander("BubbleMaps — Distribucion de holders"):
            st.markdown("""
**URL:** [bubblemaps.io](https://bubblemaps.io)

**Que es:** Visualizacion de la distribucion de holders de un token. Muestra cada wallet
como una burbuja cuyo tamano es proporcional a la cantidad de tokens que tiene.

**Como interpretarlo:**
- **Muchas burbujas pequenas:** Bueno. Distribucion amplia, menos riesgo de dump masivo
- **Una burbuja gigante:** Peligro. Una wallet tiene un porcentaje enorme del supply
- **Burbujas conectadas:** Las wallets estan relacionadas (mismo dueno probable). Muy peligroso
- **Cluster de burbujas medianas:** Puede indicar manipulacion coordinada

**Regla rapida:** Si una wallet no-exchange tiene >10% del supply, precaucion.
Si tiene >25%, alto riesgo. Si tiene >50%, practicamente garantizado rug pull.
            """)

        # --- GeckoTerminal ---
        with st.expander("GeckoTerminal — Pools y liquidez"):
            st.markdown("""
**URL:** [geckoterminal.com](https://www.geckoterminal.com)

**Que es:** Explorer de pools de liquidez en DEXs. Propiedad de CoinGecko.
Es la fuente principal de datos de Meme Detector.

**Datos utiles:**
- **Pools:** Ve todos los pools de liquidez de un token y en que DEXs estan
- **Liquidez total:** Suma de liquidez en todos los pools
- **Volumen 24h:** Actividad de trading real
- **Price chart:** Grafico de precio por pool especifico
- **OHLCV:** Datos historicos de precio (Open, High, Low, Close, Volume)

**Para que lo usa Meme Detector:**
Nuestros modelos extraen datos de GeckoTerminal para calcular features como:
volatilidad, tendencias de volumen, crecimiento de liquidez, y patrones de precio.
            """)

        # --- Meme Detector ---
        with st.expander("Meme Detector — Como interpretar nuestras senales"):
            st.markdown("""
**Meme Detector** analiza miles de memecoins diariamente con modelos de Machine Learning
para identificar aquellos con mayor probabilidad de ser "gems" (10x+).

**Score (0-100):**
- **80-100:** Senal fuerte. El modelo ve multiples indicadores positivos alineados
- **60-79:** Senal moderada. Algunos indicadores positivos, pero no todos
- **40-59:** Neutral. No hay evidencia clara en ninguna direccion
- **0-39:** Senal negativa. El modelo ve riesgo elevado

**Signal (BUY / HOLD / SELL):**
- Basada en el score + reglas adicionales de confirmacion
- BUY no significa "compra ya" — significa que el modelo ve potencial
- Siempre verifica con tu propio analisis antes de actuar

**SHAP values (explicabilidad):**
- Muestra QUE features contribuyeron mas a la senal
- Ejemplo: "liquidity_growth_7d: +0.15" = la liquidez creciente contribuyo positivamente
- Si las features principales son solidas (liquidez, volumen, holders), la senal es mas confiable
- Si dependen de features volatiles (precio a corto plazo), la senal es menos estable

**Como usar Meme Detector en tu proceso:**
1. Revisa las senales diarias como punto de partida
2. Filtra por score > 70 para ver solo las mejores oportunidades
3. Para cada token interesante, revisa el SHAP para entender POR QUE tiene score alto
4. Valida con DexScreener, BubbleMaps y tu propio analisis
5. Si todo cuadra, considera una posicion pequena (1-2% del portfolio)
6. Pon tus reglas de take-profit (2x/5x/10x) ANTES de comprar
            """)

            st.success(
                "**Recuerda:** Meme Detector es una herramienta de DETECCION, no de prediccion. "
                "Te ayuda a encontrar tokens con buenas metricas, pero la decision final siempre es tuya."
            )
