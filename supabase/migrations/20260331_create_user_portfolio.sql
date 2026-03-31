-- Migration: create_user_portfolio
-- Date: 2026-03-31
-- Description: Almacenamiento persistente del portfolio de usuarios en la nube.
--   Reemplaza el session_state-only approach del dashboard.

CREATE TABLE IF NOT EXISTS user_portfolio (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    token_id text NOT NULL,
    token_symbol text,
    token_name text,
    chain text,
    entry_price double precision,
    quantity double precision,
    notes text,
    status text DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    closed_price double precision,
    closed_at timestamptz,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- RLS
ALTER TABLE user_portfolio ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own portfolio" ON user_portfolio
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Service role full access" ON user_portfolio
    FOR ALL USING (current_setting('role') = 'service_role');

-- Index
CREATE INDEX IF NOT EXISTS idx_portfolio_user ON user_portfolio(user_id);
