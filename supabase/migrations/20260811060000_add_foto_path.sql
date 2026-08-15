-- Fotografía del contribuyente para subir en RUAT (paso Registrar Imágenes)
ALTER TABLE public.documents ADD COLUMN IF NOT EXISTS foto_path text;
COMMENT ON COLUMN public.documents.foto_path IS 'Ruta en storage de la fotografía del contribuyente (objetivo ≤90KB)';
