-- Operadores activables/desactivables por el admin (sin tokens en el PC)
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS activo boolean NOT NULL DEFAULT true;

COMMENT ON COLUMN public.profiles.activo IS 'Si false, el operador no puede iniciar sesión ni operar';
