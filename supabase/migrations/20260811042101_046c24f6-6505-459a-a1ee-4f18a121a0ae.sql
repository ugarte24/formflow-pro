-- Extensiones requeridas (gen_random_uuid / gen_random_bytes)
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;

-- ROLES
CREATE TYPE public.app_role AS ENUM ('admin', 'operador');

CREATE TABLE public.profiles (
  id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  nombre_completo text,
  telefono text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.profiles TO authenticated;
GRANT ALL ON public.profiles TO service_role;
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

CREATE TABLE public.user_roles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role public.app_role NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, role)
);
GRANT SELECT ON public.user_roles TO authenticated;
GRANT ALL ON public.user_roles TO service_role;
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION public.has_role(_user_id uuid, _role public.app_role)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.user_roles WHERE user_id = _user_id AND role = _role
  )
$$;

CREATE POLICY "profiles_select_own" ON public.profiles FOR SELECT TO authenticated
  USING (id = auth.uid() OR public.has_role(auth.uid(), 'admin'));
CREATE POLICY "profiles_insert_own" ON public.profiles FOR INSERT TO authenticated
  WITH CHECK (id = auth.uid());
CREATE POLICY "profiles_update_own" ON public.profiles FOR UPDATE TO authenticated
  USING (id = auth.uid() OR public.has_role(auth.uid(), 'admin'))
  WITH CHECK (id = auth.uid() OR public.has_role(auth.uid(), 'admin'));

CREATE POLICY "user_roles_select" ON public.user_roles FOR SELECT TO authenticated
  USING (user_id = auth.uid() OR public.has_role(auth.uid(), 'admin'));
CREATE POLICY "user_roles_admin_write" ON public.user_roles FOR ALL TO authenticated
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- COMPUTADORES AUTORIZADOS
CREATE TABLE public.computers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre text NOT NULL,
  codigo text NOT NULL UNIQUE,
  agent_token text NOT NULL DEFAULT encode(extensions.gen_random_bytes(24), 'hex'),
  activo boolean NOT NULL DEFAULT true,
  last_seen_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.computers TO authenticated;
GRANT ALL ON public.computers TO service_role;
ALTER TABLE public.computers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "computers_select_auth" ON public.computers FOR SELECT TO authenticated
  USING (activo OR public.has_role(auth.uid(), 'admin'));
CREATE POLICY "computers_admin_write" ON public.computers FOR ALL TO authenticated
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- DOCUMENTOS
CREATE TYPE public.doc_status AS ENUM (
  'capturado','procesando','datos_extraidos','pendiente_revision','confirmado',
  'enviado_pc','formulario_completado','registrado',
  'error_ocr','error_conexion','error_automatizacion','error_sistema','cancelado'
);

CREATE TABLE public.documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  operator_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  computer_id uuid REFERENCES public.computers(id) ON DELETE SET NULL,
  status public.doc_status NOT NULL DEFAULT 'capturado',
  numero_documento text,
  nombres text,
  apellidos text,
  genero text,
  estado_civil text,
  fecha_nacimiento text,
  barrio text,
  avenida text,
  numero_puerta text,
  confianza jsonb NOT NULL DEFAULT '{}'::jsonb,
  image_path text,
  error_message text,
  processing_ms integer,
  captured_at timestamptz NOT NULL DEFAULT now(),
  sent_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.documents TO authenticated;
GRANT ALL ON public.documents TO service_role;
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "documents_select" ON public.documents FOR SELECT TO authenticated
  USING (operator_id = auth.uid() OR public.has_role(auth.uid(), 'admin'));
CREATE POLICY "documents_insert_own" ON public.documents FOR INSERT TO authenticated
  WITH CHECK (operator_id = auth.uid());
CREATE POLICY "documents_update_own" ON public.documents FOR UPDATE TO authenticated
  USING (operator_id = auth.uid() OR public.has_role(auth.uid(), 'admin'))
  WITH CHECK (operator_id = auth.uid() OR public.has_role(auth.uid(), 'admin'));
CREATE POLICY "documents_delete_own" ON public.documents FOR DELETE TO authenticated
  USING (operator_id = auth.uid() OR public.has_role(auth.uid(), 'admin'));

CREATE INDEX documents_operator_created_idx ON public.documents (operator_id, created_at DESC);

-- HISTORIAL
CREATE TABLE public.operation_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid REFERENCES public.documents(id) ON DELETE CASCADE,
  operator_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  evento text NOT NULL,
  detalle text,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT ON public.operation_logs TO authenticated;
GRANT ALL ON public.operation_logs TO service_role;
ALTER TABLE public.operation_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "logs_select" ON public.operation_logs FOR SELECT TO authenticated
  USING (operator_id = auth.uid() OR public.has_role(auth.uid(), 'admin'));
CREATE POLICY "logs_insert_own" ON public.operation_logs FOR INSERT TO authenticated
  WITH CHECK (operator_id = auth.uid());

-- TIMESTAMPS
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = public AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END; $$;

CREATE TRIGGER profiles_updated_at BEFORE UPDATE ON public.profiles FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER computers_updated_at BEFORE UPDATE ON public.computers FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER documents_updated_at BEFORE UPDATE ON public.documents FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- PERFIL AUTOMÁTICO + PRIMER USUARIO ADMIN
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE user_count integer;
BEGIN
  INSERT INTO public.profiles (id, nombre_completo)
  VALUES (NEW.id, COALESCE(NEW.raw_user_meta_data->>'nombre_completo', NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1)))
  ON CONFLICT (id) DO NOTHING;

  SELECT count(*) INTO user_count FROM public.user_roles;
  IF user_count = 0 THEN
    INSERT INTO public.user_roles (user_id, role) VALUES (NEW.id, 'admin') ON CONFLICT DO NOTHING;
  END IF;
  INSERT INTO public.user_roles (user_id, role) VALUES (NEW.id, 'operador') ON CONFLICT DO NOTHING;
  RETURN NEW;
END; $$;

CREATE TRIGGER on_auth_user_created AFTER INSERT ON auth.users
FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- STORAGE POLICIES (bucket documentos)
CREATE POLICY "docs_read_own" ON storage.objects FOR SELECT TO authenticated
  USING (bucket_id = 'documentos' AND (auth.uid()::text = (storage.foldername(name))[1] OR public.has_role(auth.uid(), 'admin')));
CREATE POLICY "docs_insert_own" ON storage.objects FOR INSERT TO authenticated
  WITH CHECK (bucket_id = 'documentos' AND auth.uid()::text = (storage.foldername(name))[1]);
CREATE POLICY "docs_delete_own" ON storage.objects FOR DELETE TO authenticated
  USING (bucket_id = 'documentos' AND (auth.uid()::text = (storage.foldername(name))[1] OR public.has_role(auth.uid(), 'admin')));