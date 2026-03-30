-- Protege campos sensibles del perfil contra modificación desde el cliente.
-- El email debe coincidir siempre con auth.users y no puede cambiarse via
-- la tabla profiles directamente.

CREATE OR REPLACE FUNCTION protect_sensitive_profile_fields()
RETURNS TRIGGER AS $$
BEGIN
  -- No permitir que el usuario cambie su propio email via profiles
  NEW.email := OLD.email;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Crear el trigger solo si no existe
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_protect_sensitive_profile_fields'
  ) THEN
    CREATE TRIGGER trg_protect_sensitive_profile_fields
      BEFORE UPDATE ON profiles
      FOR EACH ROW
      EXECUTE FUNCTION protect_sensitive_profile_fields();
  END IF;
END;
$$;
