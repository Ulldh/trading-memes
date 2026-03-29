# Social Media Templates — Meme Detector

Plantillas listas para usar en redes sociales. Copiar y pegar, reemplazando
los valores entre `{llaves}` con datos reales del dia.

---

## 1. Twitter / X

### Bio

```
💎 Meme Detector | Detecta gems 10x en memecoins
🧠 ML analiza 5,000+ tokens diariamente (Solana, ETH, Base)
📊 F1 Score: 0.839 | Señales diarias 07:30 UTC
🔗 memedetector.es
```

### Hilo de lanzamiento (7 tweets)

**Tweet 1 (gancho):**
```
Presentamos Meme Detector 💎 — ML que analiza 5,000+ memecoins diariamente para encontrar las próximas gems 10x. El modelo acierta el 84% de las veces. Hilo 🧵👇
```

**Tweet 2 (como funciona):**
```
¿Cómo funciona? Nuestro modelo analiza 94 características por token: liquidez, holders, volumen, momentum, contratos... Todo lo que un humano no puede procesar en 5,000 tokens.
```

**Tweet 3 (credibilidad):**
```
Entrenado con +3,000 tokens históricos y 140 gems confirmados. Random Forest + XGBoost + LightGBM en ensemble. Sin hype, solo datos.
```

**Tweet 4 (propuesta de valor):**
```
¿Qué obtienes? Señales diarias a las 07:30 UTC: Score 0-100%, nivel STRONG/MEDIUM/WEAK, links a DexScreener. En tu dashboard y por Telegram.
```

**Tweet 5 (pricing):**
```
Plan Free: 3 señales/día, watchlist básica. Plan Pro ($29/m): todas las señales, búsqueda ilimitada, alertas Telegram, SHAP analysis.
```

**Tweet 6 (disclaimer):**
```
⚠️ NO somos asesores financieros. NO garantizamos resultados. Los memecoins son extremadamente volátiles. DYOR siempre.
```

**Tweet 7 (CTA):**
```
Pruébalo gratis → memedetector.es 💎 Academia incluida para aprender desde cero.
```

### Plantilla de senal diaria

Publicar cada dia a las ~08:00 UTC (despues de que n8n procese las senales).

```
💎 Señales del día — Meme Detector

🟢 $TOKEN1 (Solana) — Score: 85% STRONG
🟡 $TOKEN2 (Base) — Score: 72% MEDIUM
🟡 $TOKEN3 (Solana) — Score: 68% MEDIUM

📊 Modelo v16 | F1: 0.839
⚠️ No es consejo financiero

Más señales → memedetector.es
```

Reglas:
- STRONG (>=80%): emoji verde 🟢
- MEDIUM (>=65%): emoji amarillo 🟡
- WEAK (>=50%): emoji naranja 🟠
- Maximo 3 tokens en la version gratuita
- Siempre incluir disclaimer

### Plantilla de resumen semanal

Publicar cada lunes ~09:00 UTC.

```
📊 Resumen semanal — Meme Detector

Tokens analizados: 5,748
Señales emitidas: X
Aciertos verificados: X/X (X%)
Mejor detección: $TOKEN (+X%)

Track record completo → memedetector.es

⚠️ No es consejo financiero. DYOR.
```

### Tweets de contenido educativo (rotar entre estos)

```
¿Sabías que el 95% de los memecoins van a cero en las primeras 48 horas?

Por eso construimos un modelo ML que analiza 94 métricas antes de darte una señal.

No es intuición. Es matemáticas. 📊

memedetector.es
```

```
Las 3 señales más importantes que busca nuestro modelo:

1️⃣ Concentración de holders (Gini coefficient)
2️⃣ Ratio de liquidez vs market cap
3️⃣ Momentum de volumen (tendencia 24h)

Un humano tarda 30 min por token. Nosotros analizamos 5,000 en minutos.
```

```
¿Qué hace diferente a un "gem" de un rugpull?

✅ Liquidez creciente, no solo hype
✅ Holders distribuidos, no 3 wallets con el 80%
✅ Volumen orgánico, no wash trading

Nuestro modelo detecta estos patrones automáticamente 🧠
```

---

## 2. Telegram — Descripcion del canal

### Canal publico (@MemeDetectorSignals)

**Nombre:** Meme Detector Signals

**Descripcion:**
```
💎 Meme Detector — Señales Gratuitas

🧠 Machine Learning analiza +5,000 memecoins diariamente
📊 Modelo v16: 84% de acierto
⏰ Señales diarias 07:30 UTC (top 3 gratis)

🔒 Todas las señales + alertas → memedetector.es (Pro)
⚠️ No es consejo financiero. DYOR.
```

### Mensaje de bienvenida (pinned)

```
Bienvenido a Meme Detector 💎

Aquí recibirás señales diarias generadas por nuestro modelo de Machine Learning.

📊 Cómo leer las señales:
🟢 STRONG (80%+) — Alta probabilidad de gem
🟡 MEDIUM (65-79%) — Probabilidad moderada
🟠 WEAK (50-64%) — Señal débil, más riesgo

📌 Reglas del canal:
1. Las señales se publican a las 07:30 UTC
2. Cada señal incluye link a DexScreener
3. NO somos asesores financieros
4. Haz siempre tu propia investigación (DYOR)

🔗 Dashboard completo → memedetector.es
```

---

## 3. Notas de uso

- **Frecuencia Twitter**: 1 tweet diario (senal) + 2-3 tweets educativos por semana
- **Frecuencia Telegram**: 1 mensaje diario (automatizado via n8n)
- **Hashtags sugeridos**: #memecoins #solana #crypto #trading #ML #gems
- **Horario optimo**: 08:00-09:00 UTC (mercado activo, post-analisis)
- **Imagenes**: Captura del dashboard con las senales del dia (opcional)
- **Engagement**: Responder preguntas, RT aciertos verificados
