import { createServerFn } from "@tanstack/react-start";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";
import { z } from "zod";

const Input = z.object({
  imageBase64: z.string().min(100),
  mimeType: z.string().default("image/jpeg"),
});

const CampoSchema = z.object({
  valor: z.string().nullable().optional(),
  confianza: z.number().min(0).max(1).nullable().optional(),
});

const RespuestaSchema = z.object({
  documento_detectado: z.boolean().optional(),
  calidad_imagen: z.enum(["buena", "regular", "mala"]).optional(),
  campos: z.record(CampoSchema),
});

const SYSTEM = `Eres un motor de extracción de datos de documentos de identidad latinoamericanos.
Devuelves EXCLUSIVAMENTE un objeto JSON válido, sin texto adicional ni bloques de código.
Estructura exacta:
{
  "documento_detectado": true|false,
  "calidad_imagen": "buena"|"regular"|"mala",
  "campos": {
    "numero_documento": {"valor": string|null, "confianza": 0..1},
    "nombres": {"valor": string|null, "confianza": 0..1},
    "apellidos": {"valor": string|null, "confianza": 0..1},
    "genero": {"valor": "MASCULINO"|"FEMENINO"|null, "confianza": 0..1},
    "estado_civil": {"valor": "SOLTERO"|"CASADO"|"DIVORCIADO"|"VIUDO"|null, "confianza": 0..1},
    "fecha_nacimiento": {"valor": "DD/MM/AAAA"|null, "confianza": 0..1},
    "barrio": {"valor": string|null, "confianza": 0..1},
    "avenida": {"valor": string|null, "confianza": 0..1},
    "numero_puerta": {"valor": string|null, "confianza": 0..1}
  }
}
Reglas:
- Normaliza textos en MAYÚSCULAS sin acentos innecesarios ni signos de puntuación sobrantes.
- El número de documento solo contiene dígitos y, si existe, un complemento alfanumérico.
- Si un dato no aparece físicamente en el documento, devuelve valor null y confianza 0.
- La confianza refleja la legibilidad real de ese campo en la imagen.`;

function geminiApiKey() {
  return process.env["GEMINI_API_KEY"] || process.env["GOOGLE_GENERATIVE_AI_API_KEY"] || "";
}

export const extraerDatosDocumento = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((input: unknown) => Input.parse(input))
  .handler(async ({ data }) => {
    const key = geminiApiKey();
    if (!key) {
      throw new Error("Falta GEMINI_API_KEY en las variables de entorno del servidor (Vercel/Supabase).");
    }

    const inicio = Date.now();
    const model = process.env["GEMINI_MODEL"] || "gemini-flash-latest";
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${encodeURIComponent(key)}`;

    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        systemInstruction: { parts: [{ text: SYSTEM }] },
        contents: [
          {
            role: "user",
            parts: [
              { text: "Extrae los campos del documento de identidad de esta imagen." },
              {
                inlineData: {
                  mimeType: data.mimeType,
                  data: data.imageBase64,
                },
              },
            ],
          },
        ],
        generationConfig: {
          temperature: 0.1,
          responseMimeType: "application/json",
        },
      }),
    });

    if (res.status === 429) {
      throw new Error("Demasiadas solicitudes de lectura. Intente nuevamente en unos segundos.");
    }
    if (!res.ok) {
      const detalle = await res.text();
      console.error("gemini error", res.status, detalle);
      throw new Error("El servicio de lectura no está disponible en este momento.");
    }

    const json = (await res.json()) as {
      candidates?: { content?: { parts?: { text?: string }[] } }[];
    };
    const raw = json.candidates?.[0]?.content?.parts?.map((p) => p.text ?? "").join("") ?? "";
    const limpio = raw.replace(/```json/gi, "").replace(/```/g, "").trim();

    let parsed;
    try {
      parsed = RespuestaSchema.parse(JSON.parse(limpio));
    } catch {
      throw new Error("No se pudo interpretar la lectura del documento. Vuelva a escanear.");
    }

    const campos: Record<string, string> = {};
    const confianza: Record<string, number> = {};
    for (const [k, v] of Object.entries(parsed.campos)) {
      campos[k] = (v.valor ?? "").toString().trim();
      confianza[k] = typeof v.confianza === "number" ? v.confianza : 0;
    }

    return {
      campos,
      confianza,
      documentoDetectado: parsed.documento_detectado ?? true,
      calidadImagen: parsed.calidad_imagen ?? "buena",
      processingMs: Date.now() - inicio,
    };
  });
