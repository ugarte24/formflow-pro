/** Utilidades alineadas al flujo RUAT (Registro Contribuyente Natural). */

export function generarCelularAleatorio(): string {
  const prefijo = Math.random() < 0.5 ? "6" : "7";
  let resto = "";
  for (let i = 0; i < 7; i++) resto += Math.floor(Math.random() * 10).toString();
  return `${prefijo}${resto}`;
}

export function partirApellidos(apellidos: string | null | undefined): {
  primer_apellido: string;
  segundo_apellido: string;
} {
  const partes = (apellidos ?? "").trim().split(/\s+/).filter(Boolean);
  if (partes.length === 0) return { primer_apellido: "", segundo_apellido: "" };
  if (partes.length === 1) return { primer_apellido: partes[0]!, segundo_apellido: "" };
  return {
    primer_apellido: partes[0]!,
    segundo_apellido: partes.slice(1).join(" "),
  };
}
