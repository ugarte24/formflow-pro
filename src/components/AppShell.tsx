import { Link, useRouter } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Home, History, User, ScanLine, Shield, LogOut } from "lucide-react";
import type { ReactNode } from "react";
import { supabase } from "@/integrations/supabase/client";
import { ConnectionBadge } from "@/components/ConnectionBadge";
import { BrandMark } from "@/components/BrandMark";

export function AppShell({
  children,
  titulo,
  subtitulo,
  esAdmin,
  accion,
  fill,
}: {
  children: ReactNode;
  titulo: string;
  subtitulo?: string | undefined;
  esAdmin?: boolean | undefined;
  accion?: ReactNode | undefined;
  /** Pantalla a altura del viewport sin scroll (p. ej. escanear). */
  fill?: boolean | undefined;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();

  async function salir() {
    await queryClient.cancelQueries();
    queryClient.clear();
    await supabase.auth.signOut();
    router.navigate({ to: "/auth", replace: true });
  }

  return (
    <div
      className={
        fill
          ? "flex h-dvh flex-col overflow-hidden bg-background"
          : "min-h-screen bg-background pb-24"
      }
    >
      <header className="sticky top-0 z-20 shrink-0 border-b border-border bg-surface/90 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center gap-3 px-4 py-3.5">
          <BrandMark className="h-8 w-8" iconClassName="h-4 w-4" />
          <div className="min-w-0 flex-1">
            <p className="label-caps">Digitalizador</p>
            <h1 className="truncate text-lg leading-tight font-semibold">{titulo}</h1>
            {subtitulo ? <p className="truncate text-xs text-muted-foreground">{subtitulo}</p> : null}
          </div>
          {accion}
          <ConnectionBadge />
          <button
            onClick={salir}
            aria-label="Cerrar sesión"
            className="rounded-lg border border-border p-2 text-muted-foreground transition-colors hover:bg-muted"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </header>

      <main
        className={
          fill
            ? "mx-auto flex min-h-0 w-full max-w-3xl flex-1 flex-col px-4 py-2"
            : "mx-auto max-w-3xl px-4 py-5"
        }
      >
        {children}
      </main>

      <nav
        className={
          fill
            ? "z-20 shrink-0 border-t border-border bg-surface/95 backdrop-blur"
            : "fixed inset-x-0 bottom-0 z-20 border-t border-border bg-surface/95 backdrop-blur"
        }
      >
        <div className="mx-auto flex max-w-3xl items-stretch justify-around px-2 py-1.5">
          <NavItem to="/inicio" icon={<Home className="h-5 w-5" />} label="Inicio" />
          <NavItem to="/escanear" icon={<ScanLine className="h-5 w-5" />} label="Escanear" />
          <NavItem to="/historial" icon={<History className="h-5 w-5" />} label="Historial" />
          {esAdmin ? <NavItem to="/admin" icon={<Shield className="h-5 w-5" />} label="Admin" /> : null}
          <NavItem to="/perfil" icon={<User className="h-5 w-5" />} label="Perfil" />
        </div>
      </nav>
    </div>
  );
}

function NavItem({ to, icon, label }: { to: string; icon: ReactNode; label: string }) {
  return (
    <Link
      to={to}
      className="flex flex-1 flex-col items-center gap-1 rounded-lg px-2 py-2 text-[11px] font-medium text-muted-foreground transition-colors hover:text-foreground"
      activeProps={{ className: "text-primary" }}
    >
      {icon}
      {label}
    </Link>
  );
}
