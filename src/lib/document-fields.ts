export type DocStatus =
  | "capturado"
  | "procesando"
  | "datos_extraidos"
  | "pendiente_revision"
  | "confirmado"
  | "enviado_pc"
  | "formulario_completado"
  | "registrado"
  | "ya_registrado"
  | "error_ocr"
  | "error_conexion"
  | "error_automatizacion"
  | "error_sistema"
  | "cancelado";

export const CAMPOS = [
  { key: "numero_documento", label: "Número de documento", type: "text" },
  { key: "nombres", label: "Nombres", type: "text" },
  { key: "apellidos", label: "Apellidos", type: "text" },
  { key: "genero", label: "Género", type: "select", options: ["MASCULINO", "FEMENINO"] },
  {
    key: "estado_civil",
    label: "Estado civil",
    type: "select",
    options: ["SOLTERO", "CASADO", "DIVORCIADO", "VIUDO"],
  },
  { key: "fecha_nacimiento", label: "Fecha de nacimiento", type: "text" },
  { key: "barrio", label: "Barrio", type: "text" },
  { key: "avenida", label: "Avenida", type: "text" },
  { key: "numero_puerta", label: "Número de puerta", type: "text" },
] as const;

export type CampoKey = (typeof CAMPOS)[number]["key"];

export type StatusTone = "neutral" | "info" | "ok" | "warn" | "bad";

export const STATUS_META: Record<DocStatus, { label: string; tone: StatusTone }> = {
  capturado: { label: "Capturado", tone: "neutral" },
  procesando: { label: "Procesando", tone: "info" },
  datos_extraidos: { label: "Datos extraídos", tone: "info" },
  pendiente_revision: { label: "Pendiente de revisión", tone: "warn" },
  confirmado: { label: "En cola — esperando agente", tone: "info" },
  enviado_pc: { label: "Procesando en el PC…", tone: "info" },
  formulario_completado: { label: "Formulario completado", tone: "ok" },
  registrado: { label: "Registrado", tone: "ok" },
  ya_registrado: { label: "Ya registrado en Riberalta", tone: "warn" },
  error_ocr: { label: "Error de lectura", tone: "bad" },
  error_conexion: { label: "Error de conexión", tone: "bad" },
  error_automatizacion: { label: "Error de automatización", tone: "bad" },
  error_sistema: { label: "Error del sistema", tone: "bad" },
  cancelado: { label: "Cancelado", tone: "bad" },
};

export const TONE_CLASS: Record<StatusTone, string> = {
  neutral: "bg-muted text-muted-foreground",
  info: "bg-accent text-accent-foreground",
  ok: "bg-success/12 text-success",
  warn: "bg-warning/20 text-warning-foreground",
  bad: "bg-destructive/12 text-destructive",
};

export const PENDIENTES: DocStatus[] = ["capturado", "procesando", "datos_extraidos", "pendiente_revision"];
export const EN_CURSO: DocStatus[] = ["confirmado", "enviado_pc", "formulario_completado"];

/** Mensajes del agente que indican CI ya en el municipio (compat. con reportes viejos). */
export function esYaRegistradoMunicipio(status: string | null | undefined, errorMessage?: string | null) {
  if (status === "ya_registrado") return true;
  if (!errorMessage) return false;
  return /ya tiene un registro|ya registrado en riberalta/i.test(errorMessage);
}

/** Meta de badge: no mostrar «Error de automatización» si solo es ya registrado. */
export function statusMetaFor(
  status: string | null | undefined,
  errorMessage?: string | null,
): { label: string; tone: StatusTone } {
  if (esYaRegistradoMunicipio(status, errorMessage)) {
    return STATUS_META.ya_registrado;
  }
  const key = (status ?? "") as DocStatus;
  return STATUS_META[key] ?? { label: status || "Desconocido", tone: "neutral" };
}

export function confianzaTone(valor: number | undefined) {
  if (valor === undefined) return "warn" as const;
  if (valor >= 0.85) return "ok" as const;
  if (valor >= 0.6) return "warn" as const;
  return "bad" as const;
}
