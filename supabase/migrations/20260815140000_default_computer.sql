-- PC único por defecto: el admin ya no registra computadores; con usuarios alcanza.
INSERT INTO public.computers (nombre, codigo, activo)
VALUES ('PC Operador', 'PC-DEFAULT', true)
ON CONFLICT (codigo) DO UPDATE SET activo = true, nombre = EXCLUDED.nombre;
