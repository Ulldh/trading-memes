# Protocolo de Mejora Continua — Memecoin Gem Detector

> Documento vivo. Actualizado: 2026-03-30. Version del modelo activo: v16.
>
> Este protocolo define las reglas automatizadas y manuales para la mejora continua
> del sistema ML de deteccion de gems. Basado en el analisis profundo de gems realizado
> en la sesion 21.

---

## A. ADN de un Gem (Que hace que un token sea gem)

### Hallazgos clave del analisis profundo

| Feature | Gems | No-Gems | p-value | Cohen's d | Interpretacion |
|---------|-------|---------|---------|-----------|----------------|
| **RSI 7d** | 67 | 31 | 6.28e-17 | **1.52** | **Predictor mas fuerte.** Gems tienen momentum alcista extremo |
| **Volume/Liquidity ratio** | 844x mayor | baseline | < 0.001 | alto | Volumen desproporcionado vs liquidez = demanda explosiva |
| **BB bandwidth** | 3.3x mayor | baseline | < 0.001 | alto | Volatilidad expandida, movimiento direccional |
| **BB %B** | 1.95x mayor | baseline | < 0.001 | alto | Precio consistentemente por encima de banda superior |
| **ATR** | 3.7x mayor | baseline | < 0.001 | alto | Rango de movimiento diario amplio |
| **Liq-to-mcap** | 38x mayor | baseline | < 0.001 | alto | Pool de liquidez profundo relativo a capitalizacion |

### Combinacion triple (regla de oro)

> **RSI + return_30d + bb_bandwidth todos por encima de la mediana = 41% tasa de gem (7.5x lift)**

Esto significa que si un token cumple las tres condiciones simultaneamente, tiene un 41% de probabilidad
de ser gem — frente al ~5.4% de la poblacion general. Es el filtro mas potente que tenemos.

### Definicion operativa de un gem

> "Un gem es un token con fuerte momentum alcista (RSI alto), alta volatilidad (Bollinger Bands expandidas,
> ATR elevado), y volumen de trading sostenido y desproporcionado respecto a su pool de liquidez."

---

## B. Problemas del Modelo Identificados

### B1. Calibracion danina con pocos gems
- **Problema**: Con <50 gems en el set de validacion, la calibracion isotonica/Platt comprime todas las
  probabilidades por debajo de 0.50, haciendo que ningun token supere el threshold
- **Impacto**: El modelo produce 0 predicciones positivas en produccion
- **Solucion**: Calibracion DESHABILITADA hasta tener 200+ gems en training

### B2. Threshold inadecuado
- **Problema**: El threshold por defecto de 0.50 es demasiado alto para un dataset desbalanceado (5.4% gems)
- **Evidencia**: Threshold 0.50 = 0 gems capturados. Threshold 0.20 = 10/16 gems (F1 = 0.526)
- **Solucion**: Tabla de thresholds dinamica basada en cantidad de gems (ver seccion H)

### B3. Feature selection sobre-agresiva
- **Problema**: El selector automatico elimino 13 features que tenian significancia estadistica real
- **Causa**: El filtro de varianza eliminaba features binarias y near-zero validas para crypto
- **Solucion**: `skip_variance=True` por defecto, threshold de importancia mas conservador

### B4. Rug pulls imitan gems
- **Problema**: En las primeras 24-48 horas, los rug pulls muestran patrones de momentum y volumen
  identicos a los gems (mismo RSI alto, mismo volumen explosivo)
- **Solucion futura**: Features temporales de deteccion de rug (velocidad de dump, remocion de liquidez)

### B5. Alta tasa de NaN en features tecnicas
- **Problema**: 43% de NaN en features de Bollinger Bands y RSI
- **Causa**: Tokens sin suficiente historial de OHLCV (necesitan minimo 14 candles para RSI)
- **Solucion**: Backfill continuo con Birdeye API. Meta: reducir NaN a <20% en 3 meses

---

## C. Ciclo Semanal Automatizado

> Configurado via `check-retrain.yml` en GitHub Actions + workflows n8n.

```
Lunes 08:00 UTC ──> Drift Detection
                         │
                    drift > threshold?
                    /              \
                  SI               NO
                  │                 │
           Auto-Retrain         Fin ciclo
                  │
           Validacion vs v16
                  │
            F1 >= baseline?
            /            \
          SI              NO
          │                │
   Deploy nuevo      Auto-Rollback
   modelo              (mantener v16)
```

### Detalle de cada paso

| Paso | Hora | Accion | Script |
|------|------|--------|--------|
| 1 | Lun 08:00 UTC | Deteccion de drift (PSI + KS test por feature) | `check_drift.py` |
| 2 | Si drift detectado | Auto-trigger retrain pipeline | `retrain_pipeline.py` |
| 3 | Retrain rapido | `--skip-labels --skip-features` (reutiliza features existentes) | `retrain_pipeline.py` |
| 4 | Post-retrain | Validacion contra baseline actual (v16) | Integrado en trainer |
| 5 | Decision automatica | Rollback si F1 del nuevo modelo < F1 baseline | Integrado en trainer |

### Alertas n8n asociadas
- **[MEME] Drift Alert** (Lunes 08:30 UTC) — Notifica si drift fue detectado
- **[MEME] Retrain Notifier** (Lunes 09:00 UTC) — Notifica resultado del retrain

---

## D. Ciclo Mensual Profundo (NUEVO — Pendiente de configurar)

> Analisis exhaustivo mensual. Mas costoso en tiempo y recursos que el semanal.
> Objetivo: detectar cambios estructurales en el mercado de memecoins.

### Pasos del ciclo mensual

| # | Paso | Descripcion | Duracion estimada |
|---|------|-------------|-------------------|
| 1 | **Pipeline completo** | Re-extraer features desde OHLCV + re-etiquetar todos los tokens | ~30 min |
| 2 | **Analisis profundo de gems** | Ejecutar analisis estadistico de gems vs no-gems | ~10 min |
| 3 | **Verificar ADN del gem** | Comparar distribucion de top features vs mes anterior | ~5 min |
| 4 | **Tuning Optuna** | Solo si F1 mejoro > 5% por acumulacion de datos | ~45 min |
| 5 | **Actualizar threshold** | Recalcular segun tabla dinamica y curva PR | ~2 min |
| 6 | **Comparar importancia de features** | Detectar features que subieron/bajaron en ranking SHAP | ~5 min |
| 7 | **Generar reporte** | Resumen automatico enviado a Telegram | ~1 min |

### Configuracion necesaria

```yaml
# .github/workflows/monthly-deep-retrain.yml
name: Monthly Deep Retrain
on:
  schedule:
    - cron: '0 6 1 * *'  # Dia 1 de cada mes, 06:00 UTC
  workflow_dispatch: {}    # Trigger manual tambien

# Pasos:
# 1. python -m src.data.collector --full
# 2. python notebooks/gem_deep_analysis.py --compare-previous
# 3. python -m src.models.trainer --full --optuna-if-improved
# 4. python scripts/generate_monthly_report.py
# 5. Notificar via Telegram
```

### Outputs esperados
- `data/reports/monthly_YYYY_MM.json` — Metricas completas del mes
- `data/reports/gem_dna_comparison_YYYY_MM.json` — Cambios en ADN del gem
- Notificacion Telegram con resumen ejecutivo

---

## E. Objetivos de Acumulacion de Datos

### Metricas actuales y proyecciones

| Metrica | Actual (2026-03-30) | Mes 2 (mayo) | Mes 3 (junio) | Mes 6 (sept) |
|---------|---------------------|---------------|----------------|---------------|
| **Gems** | 140 | 250+ | 400+ | 800+ |
| **Tokens totales** | 6,053 | 8,000+ | 10,000+ | 15,000+ |
| **OHLCV candles** | 135K | 200K+ | 300K+ | 500K+ |
| **NaN rate Bollinger** | 43% | <30% | <20% | <10% |

### Hitos de desbloqueo (por cantidad de gems)

| Gems en training | Funcionalidad desbloqueada | Impacto esperado |
|-----------------|---------------------------|------------------|
| **200+** | Re-habilitar calibracion isotonica | Probabilidades mas fiables |
| **250+** | Optuna tuning confiable | Suficientes gems en cada CV fold |
| **300+** | Walk-forward validation | Evaluacion temporal realista |
| **400+** | Features de interaccion | Captura de patrones no-lineales |
| **500+** | Stacking ensemble robusto | Combinacion optima de modelos |

### Regla de acumulacion
- El daily-collect (GitHub Actions) agrega ~50-100 tokens nuevos/dia
- De esos, ~2-5% seran eventualmente gems (despues de 30 dias de madurar)
- Velocidad estimada: ~30-50 gems nuevos/mes

---

## F. Roadmap de Feature Engineering

### Fase 1 — Ahora (v16+, en curso)
- [x] Corregir threshold con tabla dinamica
- [x] Deshabilitar calibracion isotonica
- [x] Ajustar feature selection (`skip_variance=True`)
- [ ] Reducir NaN con backfill continuo de Birdeye
- [ ] Monitorar que RSI siga siendo el predictor #1

### Fase 2 — Cuando Twitter API este activa ($100/m)
- [ ] `tweet_count_24h` — Numero de tweets mencionando el token en 24h
- [ ] `tweet_count_7d` — Idem en 7 dias
- [ ] `sentiment_score` — Score de sentimiento promedio (positive/negative/neutral)
- [ ] `influencer_mentions` — Menciones por cuentas con >10K followers
- [ ] `hashtag_momentum` — Velocidad de crecimiento del hashtag del token
- [ ] `social_volume_ratio` — Volumen social / volumen on-chain

### Fase 3 — Cuando 200+ gems (estimado: mayo 2026)
- [ ] `holder_dump_speed` — Velocidad a la que holders venden (deteccion de rug)
- [ ] `liq_removal_rate` — Tasa de remocion de liquidez del pool
- [ ] `whale_exit_pattern` — Patron de salida de top holders
- [ ] `dev_wallet_activity` — Actividad de wallets del desarrollador

### Fase 4 — Cuando 400+ gems (estimado: julio 2026)
- [ ] `rsi_x_bb_bandwidth` — Interaccion RSI * Bollinger bandwidth
- [ ] `volume_ratio_x_holder_count` — Interaccion volumen/liquidez * holders
- [ ] `return_7d_x_liq_depth` — Interaccion retorno * profundidad de liquidez
- [ ] Features polinomicas de las top-5 features SHAP

---

## G. Estrategia de Seleccion de Modelo

### Roles de cada modelo

| Modelo | Rol | Fortaleza | Debilidad |
|--------|-----|-----------|-----------|
| **XGBoost** | **Primario** | Mejor F1 en threshold optimo, buen balance precision/recall | Puede overfit con pocos gems |
| **Random Forest** | Secundario | Mayor recall en thresholds bajos, mas estable | Precision menor |
| **LightGBM** | Monitor | Rapido de entrenar, CV F1 prometedor | Overfitting en validacion con pocos gems |
| **Ensemble** | Futuro | Potencialmente mejor que cualquier individual | Requiere calibracion funcional (200+ gems) |

### Regla de seleccion automatica (implementada en trainer.py)

```python
# Pseudo-codigo de la logica de seleccion
if gems_count >= 200 and ensemble_f1 > best_single_f1 * 1.02:
    best_model = "ensemble"
elif xgb_f1 >= rf_f1:
    best_model = "xgboost"
else:
    best_model = "random_forest"

# LightGBM solo se selecciona si supera a ambos por >5%
if lgb_f1 > max(xgb_f1, rf_f1) * 1.05:
    best_model = "lightgbm"
```

### Cuando cambiar de estrategia
- Si XGBoost domina consistentemente 3+ retrains: considerar enfocarse solo en XGBoost + tuning
- Si Ensemble empieza a ganar con 200+ gems: migrar a ensemble como primario
- Si un modelo nuevo (CatBoost, etc.) muestra mejoras: agregar al pipeline

---

## H. Gestion de Threshold

### Tabla dinamica por cantidad de gems en training

| Gems en training | Threshold recomendado | Logica |
|-----------------|----------------------|--------|
| < 100 | **0.20** | Maximizar recall, aceptar falsos positivos. Pocos gems = cada uno cuenta |
| 100 - 200 | **0.25** | Balance conservador. Empezamos a tener suficientes datos |
| 200 - 300 | **0.30** | Calibracion empieza a funcionar, podemos ser mas exigentes |
| > 300 | **Optimo calculado** | Usar threshold optimo de la curva Precision-Recall del trainer |

### Implementacion tecnica
- **Trainer**: Escribe el threshold en `metadata.json` basado en esta tabla
- **Scorer**: Lee threshold de `metadata.json` al iniciar
- **Override manual**: Variable de entorno `SCORE_THRESHOLD` (prioridad maxima)
- **Dashboard**: Muestra threshold actual en la pagina de admin

### Ejemplo metadata.json
```json
{
  "model_version": "v16",
  "threshold": 0.25,
  "threshold_source": "dynamic_table",
  "gems_in_training": 140,
  "optimal_threshold_pr": 0.22,
  "note": "Using dynamic table (100-200 gems range)"
}
```

---

## I. Metricas Clave a Monitorear

### Metricas primarias (monitoreadas semanalmente)

| Metrica | Valor actual | Objetivo corto plazo | Objetivo largo plazo | Umbral critico |
|---------|-------------|---------------------|---------------------|----------------|
| **AUC** | 0.89 | > 0.90 | > 0.93 | < 0.85 (URGENTE) |
| **F1 @ threshold optimo** | 0.526 | > 0.60 | > 0.75 | < 0.40 (investigar) |
| **Gem capture rate (recall)** | ~0.60 | > 0.60 | > 0.75 | < 0.40 |
| **False positive rate** | ~8% | < 5% | < 3% | > 15% |

### Metricas secundarias (monitoreadas mensualmente)

| Metrica | Valor actual | Descripcion | Tendencia esperada |
|---------|-------------|-------------|-------------------|
| **Triple combo gem rate** | 41% | Tasa de gem con RSI+return+BB altos | Estable o mejorando |
| **NaN rate features** | 43% | % de NaN en Bollinger/RSI | Bajando (backfill) |
| **Gems en training** | 140 | Cantidad de gems etiquetados | Subiendo ~40/mes |
| **Feature drift score** | monitorado | PSI/KS por feature | Estable |
| **Top feature stability** | RSI #1 | Si el top predictor cambia | Monitorar cambios |

### Dashboard de metricas
- Pagina admin del dashboard muestra metricas de drift en tiempo real
- Historial de versiones con metricas en tabla `model_versions` de Supabase
- Graficos de tendencia en notebook 08

---

## J. Reglas de Alerta

### Matriz de alertas automaticas

| Condicion | Severidad | Canal | Accion automatica | Accion manual requerida |
|-----------|-----------|-------|-------------------|------------------------|
| AUC < 0.85 | **URGENTE** | Telegram inmediato | Retrain automatico | Revisar si hay cambio estructural |
| F1 < 0.40 | **ALTA** | Telegram | Retrain automatico | Investigar feature drift |
| Gem count < 100 | **MEDIA** | Telegram semanal | Reducir threshold a 0.20 | Revisar pipeline de labeling |
| NaN rate > 50% | **ALTA** | Telegram | Ninguna | Investigar OHLCV pipeline / Birdeye |
| Drift score > threshold | **MEDIA** | Telegram | Trigger retrain | Ninguna (automatico) |
| Retrain falla 2x consecutivas | **ALTA** | Telegram | Ninguna | Revisar logs, debug pipeline |
| 0 scores generados en 7 dias | **URGENTE** | Telegram | Ninguna | Verificar scorer, threshold, pipeline |

### Niveles de escalado

1. **Automatico** (semanal): Retrain + validacion + rollback si necesario. Sin intervencion humana.
2. **Semi-automatico** (mensual): Notificacion Telegram + revision dashboard de drift. Humano decide si hacer deep retrain.
3. **Manual** (trimestral): Revision completa del ADN de gems, feature engineering, estrategia de modelo. Requiere sesion de analisis.

### Workflow de escalado
```
Alerta detectada
       │
  Es automatizable? ──SI──> Ejecutar accion automatica
       │                            │
      NO                     Resolvio el problema?
       │                     /              \
  Notificar Telegram       SI              NO
       │                    │               │
  Esperar accion       Fin alerta     Escalar a manual
  manual humana                            │
                                    Programar sesion
                                    de analisis
```

---

## Apendice: Comandos Utiles

```bash
# Verificar estado actual del modelo
python -c "from src.models.trainer import ModelTrainer; t = ModelTrainer(); print(t.get_current_version())"

# Ejecutar drift check manualmente
python scripts/check_drift.py

# Retrain manual completo
python scripts/retrain_pipeline.py --full

# Retrain rapido (reutilizar features)
python scripts/retrain_pipeline.py --skip-labels --skip-features

# Ver metricas del modelo actual
python -c "import json; print(json.dumps(json.load(open('data/models/latest/metadata.json')), indent=2))"

# Contar gems actuales
python -c "from src.data.storage import get_storage; s = get_storage(); print(s.query('SELECT COUNT(*) FROM labels WHERE is_gem = true'))"
```

---

## Historial de Versiones del Protocolo

| Fecha | Version | Cambios |
|-------|---------|---------|
| 2026-03-30 | 1.0 | Creacion inicial basada en analisis profundo de gems (sesion 21) |

---

> **Nota**: Este documento se actualiza automaticamente tras cada ciclo mensual profundo.
> Los valores de "Actual" se actualizan con cada retrain exitoso.
