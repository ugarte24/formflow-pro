import { createServerFn } from "@tanstack/react-start";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";

const BUCKET = "agente";
const PATH = "releases/DigitalizadorAgent-Setup.zip";
const META_PATH = "releases/version.json";

async function asegurarAdmin(supabase: any, userId: string) {
  const { data } = await supabase.rpc("has_role", { _user_id: userId, _role: "admin" });
  if (!data) throw new Error("Solo un administrador puede realizar esta acción");
}

export const estadoInstaladorAgente = createServerFn({ method: "GET" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    await asegurarAdmin(context.supabase, context.userId);
    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");

    const [{ data: files, error }, metaRes] = await Promise.all([
      supabaseAdmin.storage.from(BUCKET).list("releases", {
        search: "DigitalizadorAgent-Setup.zip",
        limit: 5,
      }),
      supabaseAdmin.storage.from(BUCKET).download(META_PATH),
    ]);
    if (error) throw new Error(error.message);

    const file = (files ?? []).find((f) => f.name === "DigitalizadorAgent-Setup.zip");
    if (!file) return { disponible: false as const };

    let version: string | null = null;
    let publicado: string | null = file.updated_at ?? file.created_at ?? null;
    let bytes: number | null = file.metadata?.size ?? null;

    if (metaRes.data && !metaRes.error) {
      try {
        const raw = metaRes.data;
        const text =
          typeof (raw as Blob).text === "function"
            ? await (raw as Blob).text()
            : new TextDecoder().decode(raw as ArrayBuffer);
        const meta = JSON.parse(text) as {
          version?: string;
          bytes?: number;
          publicado_at?: string;
        };
        version = meta.version ?? null;
        if (typeof meta.bytes === "number") bytes = meta.bytes;
        if (meta.publicado_at) publicado = meta.publicado_at;
      } catch {
        /* ignore meta parse */
      }
    }

    return {
      disponible: true as const,
      nombre: file.name,
      version,
      bytes,
      actualizado: publicado,
    };
  });

export const urlDescargaInstaladorAgente = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    await asegurarAdmin(context.supabase, context.userId);
    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");

    let version = "1.0.0";
    const metaRes = await supabaseAdmin.storage.from(BUCKET).download(META_PATH);
    if (metaRes.data && !metaRes.error) {
      try {
        const raw = metaRes.data;
        const text =
          typeof (raw as Blob).text === "function"
            ? await (raw as Blob).text()
            : new TextDecoder().decode(raw as ArrayBuffer);
        const meta = JSON.parse(text) as { version?: string };
        if (meta.version) version = meta.version;
      } catch {
        /* ignore */
      }
    }

    const fileName = `DigitalizadorAgent-Setup-v${version}.zip`;
    const { data, error } = await supabaseAdmin.storage.from(BUCKET).createSignedUrl(PATH, 60 * 30, {
      download: fileName,
    });
    if (error || !data?.signedUrl) {
      throw new Error(error?.message ?? "No hay instalador publicado todavía.");
    }
    return {
      url: data.signedUrl,
      nombre: fileName,
      version,
    };
  });

export type RolUsuario = "operador" | "admin";

export const crearUsuarioApp = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator(
    (input: {
      email: string;
      password: string;
      nombreCompleto: string;
      telefono?: string;
      rol: RolUsuario;
    }) => {
      const email = input?.email?.trim().toLowerCase() ?? "";
      const password = input?.password ?? "";
      const nombreCompleto = input?.nombreCompleto?.trim() ?? "";
      const telefono = input?.telefono?.trim() ?? "";
      const rol = input?.rol === "admin" ? "admin" : "operador";

      if (!email || !email.includes("@")) throw new Error("Correo no válido");
      if (password.length < 6) throw new Error("La contraseña debe tener al menos 6 caracteres");
      if (!nombreCompleto) throw new Error("Indique el nombre completo");
      if (nombreCompleto.length > 120) throw new Error("Nombre demasiado largo");
      if (telefono.length > 40) throw new Error("Teléfono demasiado largo");

      return { email, password, nombreCompleto, telefono, rol };
    },
  )
  .handler(async ({ data, context }) => {
    await asegurarAdmin(context.supabase, context.userId);
    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");

    const { data: created, error } = await supabaseAdmin.auth.admin.createUser({
      email: data.email,
      password: data.password,
      email_confirm: true,
      user_metadata: { nombre_completo: data.nombreCompleto },
    });
    if (error) throw new Error(error.message);
    const userId = created.user?.id;
    if (!userId) throw new Error("No se pudo crear el usuario");

    const { error: perfilErr } = await supabaseAdmin
      .from("profiles")
      .update({
        nombre_completo: data.nombreCompleto,
        telefono: data.telefono || null,
        activo: true,
      })
      .eq("id", userId);
    if (perfilErr) throw new Error(perfilErr.message);

    // El trigger ya asigna rol "operador". Si pidieron admin, lo agregamos.
    if (data.rol === "admin") {
      const { error: rolErr } = await supabaseAdmin.from("user_roles").insert({
        user_id: userId,
        role: "admin",
      });
      if (rolErr && !rolErr.message.toLowerCase().includes("duplicate")) {
        throw new Error(rolErr.message);
      }
    }

    return {
      id: userId,
      email: data.email,
      nombreCompleto: data.nombreCompleto,
      rol: data.rol,
    };
  });
