-- Bucket para el instalador Windows del agente (solo admin)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'agente',
  'agente',
  false,
  104857600, -- 100 MB
  ARRAY['application/zip', 'application/x-zip-compressed', 'application/octet-stream']
)
ON CONFLICT (id) DO UPDATE SET
  file_size_limit = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types;

-- Solo administradores pueden listar / bajar / subir / borrar el instalador
CREATE POLICY "agente_admin_select"
  ON storage.objects FOR SELECT TO authenticated
  USING (bucket_id = 'agente' AND public.has_role(auth.uid(), 'admin'));

CREATE POLICY "agente_admin_insert"
  ON storage.objects FOR INSERT TO authenticated
  WITH CHECK (bucket_id = 'agente' AND public.has_role(auth.uid(), 'admin'));

CREATE POLICY "agente_admin_update"
  ON storage.objects FOR UPDATE TO authenticated
  USING (bucket_id = 'agente' AND public.has_role(auth.uid(), 'admin'))
  WITH CHECK (bucket_id = 'agente' AND public.has_role(auth.uid(), 'admin'));

CREATE POLICY "agente_admin_delete"
  ON storage.objects FOR DELETE TO authenticated
  USING (bucket_id = 'agente' AND public.has_role(auth.uid(), 'admin'));
