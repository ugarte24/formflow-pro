import { createFileRoute, useRouter } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { ScanLine, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { z } from "zod";
import { supabase } from "@/integrations/supabase/client";
import { lovable } from "@/integrations/lovable/index";

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
  nombre: z.string().trim().max(120).optional(),
});

function AuthPage() {
  const router = useRouter();
  const [modo, setModo] = useState<"login" | "registro">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [nombre, setNombre] = useState("");
  const [cargando, setCargando] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) router.navigate({ to: "/inicio", replace: true });
    });
  }, [router]);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    const parsed = esquema.safeParse({ email, password, nombre });
    if (!parsed.success) {
      toast.error(parsed.error.issues[0]?.message ?? "Datos no válidos");
      return;
    }
    setCargando(true);
    setAviso(null);
    try {
      if (modo === "login") {
        const { error } = await supabase.auth.signInWithPassword({
          email: parsed.data.email,
          password: parsed.data.password,
        });
        if (error) throw error;
        router.navigate({ to: "/inicio", replace: true });
      } else {
        const { data, error } = await supabase.auth.signUp({
          email: parsed.data.email,
          password: parsed.data.password,
          options: {
            emailRedirectTo: window.location.origin,
            data: { nombre_completo: parsed.data.nombre || parsed.data.email.split("@")[0] },
          },
        });
        if (error) throw error;
        if (data.session) router.navigate({ to: "/inicio", replace: true });
        else setAviso("Cuenta creada. Revise su correo para confirmar el acceso.");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo completar la operación");
    } finally {
      setCargando(false);
    }
  }

  async function google() {
    const result = await lovable.auth.signInWithOAuth("google", {
      redirect_uri: window.location.origin,
    });
    if (result.error) {
      toast.error("No se pudo iniciar sesión con Google");
      return;
    }
    if (result.redirected) return;
    router.navigate({ to: "/inicio", replace: true });
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
          <h1 className="mt-1 text-xl font-semibold">
            {modo === "login" ? "Iniciar sesión" : "Crear cuenta de operador"}
          </h1>

          <form onSubmit={enviar} className="mt-5 space-y-3.5">
            {modo === "registro" ? (
              <Campo label="Nombre completo" value={nombre} onChange={setNombre} placeholder="Juan Pérez" />
            ) : null}
            <Campo label="Correo" value={email} onChange={setEmail} type="email" placeholder="operador@empresa.com" />
            <Campo label="Contraseña" value={password} onChange={setPassword} type="password" placeholder="••••••••" />

            <button
              type="submit"
              disabled={cargando}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-60"
            >
              {cargando ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {modo === "login" ? "Entrar" : "Crear cuenta"}
            </button>
          </form>

          {aviso ? (
            <p className="mt-3 rounded-lg bg-accent px-3 py-2 text-xs text-accent-foreground">{aviso}</p>
          ) : null}

          <div className="my-4 flex items-center gap-3">
            <span className="h-px flex-1 bg-border" />
            <span className="label-caps">o</span>
            <span className="h-px flex-1 bg-border" />
          </div>

          <button
            onClick={google}
            className="w-full rounded-xl border border-border bg-surface px-4 py-3 text-sm font-medium transition-colors hover:bg-muted"
          >
            Continuar con Google
          </button>

          <button
            onClick={() => setModo(modo === "login" ? "registro" : "login")}
            className="mt-4 w-full text-center text-xs text-muted-foreground underline-offset-4 hover:underline"
          >
            {modo === "login" ? "No tengo cuenta, quiero registrarme" : "Ya tengo cuenta, iniciar sesión"}
          </button>
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