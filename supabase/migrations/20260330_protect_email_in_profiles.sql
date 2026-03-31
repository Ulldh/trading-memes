-- Añade email a los campos protegidos del trigger existente.
-- La función ya protegía: role, subscription_status, subscription_plan,
-- stripe_customer_id, subscription_end, max_watchlist_tokens.
-- Ahora también protege email contra modificación directa desde el cliente.

CREATE OR REPLACE FUNCTION protect_sensitive_profile_fields()
RETURNS TRIGGER AS $$
BEGIN
    -- Only service_role can change these fields
    IF current_setting('role') != 'service_role' THEN
        NEW.role := OLD.role;
        NEW.subscription_status := OLD.subscription_status;
        NEW.subscription_plan := OLD.subscription_plan;
        NEW.stripe_customer_id := OLD.stripe_customer_id;
        NEW.subscription_end := OLD.subscription_end;
        NEW.max_watchlist_tokens := OLD.max_watchlist_tokens;
        NEW.email := OLD.email;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
