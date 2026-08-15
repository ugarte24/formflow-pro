import { createFileRoute, useRouter } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { ScanLine, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { z } from "zod";
import { supabase } from "@/integrations/supabase/client";

export const Route = createFileRoute("/auth")({
  head: () => ({
    meta: [
      { title: "Acceso de operadores — Digitalizador" },
      { name: "description", content: "Inicia sesión para escanear documentos y enviar datos al computador autorizado." },
      { property: "og:title", content: "Acceso de operadores — Digitalizador" },
      { property: "og:description", content: "Panel de operadores del sistema de digitalización." },
    ],
  }),
  component: AuthPage,
});

const esquema = z.object({
  email: z.string().trim().email("Correo no válido").max(255),
  password: z.string().min(6, "Mínimo 6 caracteres").max(72),
});

function AuthPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) router.navigate({ to: "/inicio", replace: true });
    });
  }, [router]);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    const parsed = esquema.safeParse({ email, password });
    if (!parsed.success) {
      toast.error(parsed.error.issues[0]?.message ?? "Datos no válidos");
      return;
    }
    setCargando(true);
    try {
      const { error } = await supabase.auth.signInWithPassword({
        email: parsed.data.email,
        password: parsed.data.password,
      });
      if (error) throw error;
      router.navigate({ to: "/inicio", replace: true });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo iniciar sesión");
    } finally {
      setCargando(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ScanLine className="h-5 w-5" />
          </span>
          <span className="font-display text-base font-semibold">Digitalizador</span>
        </div>

        <div className="panel mt-5 p-6">
          <p className="label-caps">Acceso</p>
          <h1 className="mt-1 text-xl font-semibold">Iniciar sesión</h1>
          <p className="mt-1.5 text-xs text-muted-foreground">
            Las cuentas las otorga el administrador. Si no tienes acceso, solicita una.
          </p>

          <form onSubmit={enviar} className="mt-5 space-y-3.5">
            <Campo label="Correo" value={email} onChange={setEmail} type="email" placeholder="operador@empresa.com" />
            <Campo label="Contraseña" value={password} onChange={setPassword} type="password" placeholder="••••••••" />

            <button
              type="submit"
              disabled={cargando}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-60"
            >
              {cargando ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Entrar
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

function Campo({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="label-caps">{label}</span>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1.5 w-full rounded-xl border border-input bg-background px-3.5 py-2.5 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-ring/25"
      />
    </label>
  );
}
