import { createServerFn } from "@tanstack/react-start";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";

const BUCKET = "agente";
const PATH = "releases/DigitalizadorAgent-Setup.zip";

async function asegurarAdmin(supabase: any, userId: string) {
  const { data } = await supabase.rpc("has_role", { _user_id: userId, _role: "admin" });
  if (!data) throw new Error("Solo un administrador puede realizar esta acción");
}

export const estadoInstaladorAgente = createServerFn({ method: "GET" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    await asegurarAdmin(context.supabase, context.userId);
    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
    const { data, error } = await supabaseAdmin.storage.from(BUCKET).list("releases", {
      search: "DigitalizadorAgent-Setup.zip",
      limit: 5,
    });
    if (error) throw new Error(error.message);
    const file = (data ?? []).find((f) => f.name === "DigitalizadorAgent-Setup.zip");
    if (!file) return { disponible: false as const };

    return {
      disponible: true as const,
      nombre: file.name,
      bytes: file.metadata?.size ?? null,
      actualizado: file.updated_at ?? file.created_at ?? null,
    };
  });

export const urlDescargaInstaladorAgente = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    await asegurarAdmin(context.supabase, context.userId);
    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
    const { data, error } = await supabaseAdmin.storage.from(BUCKET).createSignedUrl(PATH, 60 * 30);
    if (error || !data?.signedUrl) {
      throw new Error(
        error?.message ??
          "No hay instalador publicado. Subí el ZIP desde Admin o con el script de publicación.",
      );
    }
    return { url: data.signedUrl, nombre: "DigitalizadorAgent-Setup.zip" };
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
