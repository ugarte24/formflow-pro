import { createFileRoute, Link } from "@tanstack/react-router";
import { ScanLine, Cpu, ShieldCheck, Timer, ArrowRight } from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Digitalizador — Escanea, verifica y automatiza formularios" },
      {
        name: "description",
        content:
          "Captura documentos de identidad desde el celular, extrae los datos con IA y complétalos en el sistema empresarial en menos de un minuto.",
      },
      { property: "og:title", content: "Digitalizador — Automatización de formularios" },
      {
        property: "og:description",
        content: "De 10 minutos de digitación manual a menos de 1 minuto por registro.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Index() {
  return (
    <div className="min-h-screen bg-background">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-5 py-5">
        <div className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ScanLine className="h-5 w-5" />
          </span>
          <span className="font-display text-base font-semibold">Digitalizador</span>
        </div>
        <Link
          to="/auth"
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
        >
          Iniciar sesión
        </Link>
      </header>

      <main className="mx-auto max-w-5xl px-5 pb-20">
        <section className="ink-panel mt-4 px-6 py-12 sm:px-12 sm:py-16">
          <p className="label-caps text-primary-foreground/60">Operación de registro asistida</p>
          <h1 className="mt-4 max-w-2xl text-3xl leading-[1.1] font-semibold sm:text-5xl">
            Escanear, verificar y registrar en menos de un minuto.
          </h1>
          <p className="mt-5 max-w-xl text-sm leading-relaxed text-primary-foreground/70 sm:text-base">
            El operador escanea el documento de identidad con el celular. La lectura automática estructura
            los datos, el operador los valida y el agente de escritorio completa el formulario del sistema
            empresarial en Firefox.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link
              to="/auth"
              className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground"
              style={{ boxShadow: "var(--shadow-focus)" }}
            >
              Entrar al panel del operador
              <ArrowRight className="h-4 w-4" />
            </Link>
            <span className="font-mono text-xs text-primary-foreground/60">
              10 min → &lt; 60 s por registro
            </span>
          </div>
        </section>

        <section className="mt-6 grid gap-4 sm:grid-cols-3">
          <Feature
            icon={<ScanLine className="h-5 w-5" />}
            titulo="Captura guiada"
            texto="Detección de bordes, control de nitidez e iluminación antes de procesar la imagen."
          />
          <Feature
            icon={<ShieldCheck className="h-5 w-5" />}
            titulo="Validación humana"
            texto="Los campos con baja confianza se destacan y nada se envía sin la confirmación del operador."
          />
          <Feature
            icon={<Cpu className="h-5 w-5" />}
            titulo="Agente de escritorio"
            texto="El PC autorizado recibe los datos y llena el formulario sin modificar el sistema empresarial."
          />
        </section>

        <section className="panel mt-6 p-6">
          <p className="label-caps">Flujo del MVP</p>
          <ol className="mt-4 grid gap-3 text-sm sm:grid-cols-5">
            {["Escanear", "Extraer", "Verificar", "Enviar al PC", "Registrar"].map((paso, i) => (
              <li key={paso} className="rounded-xl border border-border bg-background px-3 py-3">
                <span className="font-mono text-xs text-primary">0{i + 1}</span>
                <p className="mt-1 font-medium">{paso}</p>
              </li>
            ))}
          </ol>
          <p className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
            <Timer className="h-4 w-4" /> El formulario queda completado y el guardado final sigue siendo
            una decisión del operador.
          </p>
        </section>
      </main>
    </div>
  );
}

function Feature({ icon, titulo, texto }: { icon: React.ReactNode; titulo: string; texto: string }) {
  return (
    <div className="panel p-5">
      <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent text-accent-foreground">
        {icon}
      </span>
      <h2 className="mt-4 text-base font-semibold">{titulo}</h2>
      <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{texto}</p>
    </div>
  );
}
