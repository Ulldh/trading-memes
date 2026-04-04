-- Migracion: Crear tabla alert_history para deduplicar alertas de Telegram.
-- Evita enviar la misma alerta (mismo token + senal) mas de una vez al usuario.

CREATE TABLE IF NOT EXISTS alert_history (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    token_id text NOT NULL,
    signal text NOT NULL CHECK (signal IN ('STRONG', 'MEDIUM', 'WEAK')),
    chain text,
    symbol text,
    probability double precision,
    sent_at timestamptz DEFAULT now(),
    UNIQUE(user_id, token_id, signal)
);

-- Indice para consultas rapidas de historial por usuario
CREATE INDEX IF NOT EXISTS idx_alert_history_user_sent
    ON alert_history(user_id, sent_at DESC);

-- RLS: usuarios solo ven sus propias alertas
ALTER TABLE alert_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users read own alert history" ON alert_history
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Service role full access on alert_history" ON alert_history
    FOR ALL USING (current_setting('role') = 'service_role');
