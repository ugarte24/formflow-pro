import { useQuery } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";

export function useSesion() {
  return useQuery({
    queryKey: ["sesion"],
    queryFn: async () => {
      const { data: userData } = await supabase.auth.getUser();
      const user = userData.user;
      if (!user) return null;

      const [{ data: perfil }, { data: roles }] = await Promise.all([
        supabase.from("profiles").select("*").eq("id", user.id).maybeSingle(),
        supabase.from("user_roles").select("role").eq("user_id", user.id),
      ]);

      if (perfil && perfil.activo === false) {
        await supabase.auth.signOut();
        return null;
      }

      return {
        userId: user.id,
        email: user.email ?? "",
        nombre: perfil?.nombre_completo ?? user.email?.split("@")[0] ?? "Operador",
        telefono: perfil?.telefono ?? "",
        activo: perfil?.activo !== false,
        esAdmin: (roles ?? []).some((r) => r.role === "admin"),
      };
    },
    staleTime: 60_000,
  });
}