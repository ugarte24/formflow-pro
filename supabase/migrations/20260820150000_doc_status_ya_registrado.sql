-- Estado cuando el CI ya existe en el municipio local (Riberalta).
ALTER TYPE public.doc_status ADD VALUE IF NOT EXISTS 'ya_registrado';
