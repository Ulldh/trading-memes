-- Migracion: Crear tabla alert_preferences para persistir configuracion de alertas Telegram.
-- Reemplaza el almacenamiento solo en session_state con persistencia real en Supabase.

CREATE TABLE IF NOT EXISTS alert_preferences (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    telegram_chat_id text,
    min_signal text DEFAULT 'STRONG' CHECK (min_signal IN ('STRONG', 'MEDIUM', 'WEAK')),
    chains jsonb DEFAULT '["solana", "ethereum", "base"]'::jsonb,
    min_probability double precision DEFAULT 0.6,
    enabled boolean DEFAULT true,
    quiet_hours_start integer,
    quiet_hours_end integer,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    UNIQUE(user_id)
);

-- RLS
ALTER TABLE alert_preferences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own alerts" ON alert_preferences
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Service role full access" ON alert_preferences
    FOR ALL USING (current_setting('role') = 'service_role');
