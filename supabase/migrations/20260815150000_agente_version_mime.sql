-- Permitir metadata de versión del instalador (version.json)
UPDATE storage.buckets
SET allowed_mime_types = ARRAY[
  'application/zip',
  'application/x-zip-compressed',
  'application/octet-stream',
  'application/json',
  'text/plain'
]
WHERE id = 'agente';
