import { createFileRoute, useRouter } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Camera, Check, Loader2, Send, X, RotateCcw, UserRound } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { supabase } from "@/integrations/supabase/client";
import { useSesion } from "@/hooks/useSesion";
import { canvasToJpegUnderLimit } from "@/lib/image-compress";
import { CAMPOS, STATUS_META, TONE_CLASS, confianzaTone, type DocStatus } from "@/lib/document-fields";

export const Route = createFileRoute("/_authenticated/verificar/$id")({
  head: () => ({
    meta: [
      { title: "Verificar datos extraídos — Digitalizador" },
      { name: "description", content: "Revisa y corrige los datos leídos antes de enviarlos al PC del operador." },
      { property: "og:title", content: "Verificar datos extraídos — Digitalizador" },
      { property: "og:description", content: "Validación humana antes de automatizar el formulario." },
    ],
  }),
  component: Verificar,
});

function Verificar() {
  const { id } = Route.useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: sesion } = useSesion();
  const [valores, setValores] = useState<Record<string, string>>({});
  const [guardando, setGuardando] = useState(false);
  const [capturandoFoto, setCapturandoFoto] = useState(false);
  const [camaraActiva, setCamaraActiva] = useState(false);
  const [camaraEstado, setCamaraEstado] = useState<"iniciando" | "listo" | "error">("iniciando");
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const { data: doc, refetch } = useQuery({
    queryKey: ["documento", id],
    queryFn: async () => {
      const { data, error } = await supabase.from("documents").select("*").eq("id", id).single();
      if (error) throw error;
      return data;
    },
    refetchInterval: (query) =>
      ["confirmado", "enviado_pc"].includes((query.state.data?.status as string) ?? "") ? 4000 : false,
  });

  useEffect(() => {
    if (!doc) return;
    const iniciales: Record<string, string> = {};
    for (const campo of CAMPOS) iniciales[campo.key] = (doc[campo.key] as string | null) ?? "";
    setValores(iniciales);
  }, [doc]);

  const detenerCamara = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setCamaraActiva(false);
    setCamaraEstado("iniciando");
  }, []);

  useEffect(() => () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => {
    if (!camaraActiva) return;
    let cancelled = false;
    (async () => {
      setCamaraEstado("iniciando");
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 } },
          audio: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play().catch(() => undefined);
        }
        setCamaraEstado("listo");
      } catch {
        if (!cancelled) {
          setCamaraEstado("error");
          toast.error("No se pudo abrir la cámara. Revise los permisos.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [camaraActiva]);

  function abrirCamaraFoto() {
    setCamaraActiva(true);
  }

  async function guardarFotoDesdeCamara() {
    if (!doc || !sesion || capturandoFoto) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) {
      toast.error("Cámara no lista");
      return;
    }
    setCapturandoFoto(true);
    try {
      const ancho = Math.min(1600, video.videoWidth || 1280);
      const alto = Math.round((ancho / (video.videoWidth || 1)) * (video.videoHeight || 720));
      canvas.width = ancho;
      canvas.height = alto;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("No se pudo procesar la imagen");
      ctx.drawImage(video, 0, 0, ancho, alto);

      const { blob, bytes } = await canvasToJpegUnderLimit(canvas, 90 * 1024);
      const nombre = `${sesion.userId}/${Date.now()}-foto.jpg`;
      const { error: upErr } = await supabase.storage.from("documentos").upload(nombre, blob, {
        contentType: "image/jpeg",
      });
      if (upErr) throw upErr;

      const { error: updErr } = await supabase.from("documents").update({ foto_path: nombre }).eq("id", doc.id);
      if (updErr) throw updErr;

      await supabase.from("operation_logs").insert({
        document_id: doc.id,
        operator_id: sesion.userId,
        evento: "Fotografía capturada",
        detalle: `${bytes} bytes (desde verificación)`,
      });

      detenerCamara();
      toast.success(`Fotografía guardada (${Math.round(bytes / 1024)} KB)`);
      await refetch();
      queryClient.invalidateQueries({ queryKey: ["foto-url"] });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo guardar la fotografía");
    } finally {
      setCapturandoFoto(false);
    }
  }

  const confianza = (doc?.confianza ?? {}) as Record<string, number>;
  const revisar = CAMPOS.filter((c) => (confianza[c.key] ?? 0) < 0.85 || !valores[c.key]);
  const meta = doc ? STATUS_META[doc.status as DocStatus] : null;
  const bloqueado = !!doc && ["confirmado", "enviado_pc", "formulario_completado", "registrado"].includes(doc.status);

  const { data: fotoUrl } = useQuery({
    queryKey: ["foto-url", doc?.foto_path],
    enabled: !!doc?.foto_path,
    queryFn: async () => {
      const { data } = await supabase.storage.from("documentos").createSignedUrl(doc!.foto_path!, 3600);
      return data?.signedUrl ?? null;
    },
  });

  async function confirmar() {
    if (!doc || !sesion) return;
    if (!doc.foto_path) {
      toast.error("Falta la fotografía del contribuyente. Añádala arriba.");
      return;
    }
    const faltantes = CAMPOS.filter((c) => !valores[c.key]?.trim()).map((c) => c.label);
    if (faltantes.length > 0) {
      toast.error(`Complete los campos: ${faltantes.join(", ")}`);
      return;
    }

    const { data: pcDefault } = await supabase
      .from("computers")
      .select("id")
      .eq("codigo", "PC-DEFAULT")
      .eq("activo", true)
      .maybeSingle();
    const { data: pcFallback } = pcDefault
      ? { data: null }
      : await supabase.from("computers").select("id").eq("activo", true).order("created_at").limit(1).maybeSingle();
    const computerId = pcDefault?.id ?? pcFallback?.id;
    if (!computerId) {
      toast.error("No hay PC del agente configurado. Contacte al administrador.");
      return;
    }

    setGuardando(true);
    try {
      const { error } = await supabase
        .from("documents")
        .update({
          ...valores,
          computer_id: computerId,
          status: "confirmado",
          sent_at: new Date().toISOString(),
          error_message: null,
        })
        .eq("id", doc.id);
      if (error) throw error;
      await supabase.from("operation_logs").insert({
        document_id: doc.id,
        operator_id: sesion.userId,
        evento: "Datos confirmados y enviados al PC",
      });
      toast.success("Datos enviados. Esperando al agente de escritorio…");
      await refetch();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo enviar");
    } finally {
      setGuardando(false);
    }
  }

  async function cancelar() {
    if (!doc || !sesion) return;
    detenerCamara();
    await supabase.from("documents").update({ status: "cancelado" }).eq("id", doc.id);
    await supabase.from("operation_logs").insert({
      document_id: doc.id,
      operator_id: sesion.userId,
      evento: "Documento cancelado",
    });
    router.navigate({ to: "/inicio" });
  }

  if (!doc) {
    return (
      <AppShell titulo="Verificación" esAdmin={sesion?.esAdmin}>
        <div className="panel flex items-center gap-3 p-6 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Cargando documento…
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell
      titulo="Verificación de datos"
      subtitulo={`Documento ${doc.numero_documento || "sin número"}`}
      esAdmin={sesion?.esAdmin}
      accion={
        meta ? (
          <span className={`rounded-md px-2 py-1 text-[11px] font-medium ${TONE_CLASS[meta.tone]}`}>{meta.label}</span>
        ) : null
      }
    >
      {doc.error_message && !bloqueado ? (
        <div className="mb-4 flex items-start gap-2.5 rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
          <div className="text-sm text-destructive">
            <p className="font-semibold">Error del agente</p>
            <p className="mt-0.5 text-xs opacity-90">{doc.error_message}</p>
            <p className="mt-1 text-xs text-muted-foreground">Corrija si hace falta y vuelva a enviar al PC.</p>
          </div>
        </div>
      ) : null}

      {bloqueado ? (
        <div className="panel mb-4 p-5">
          <p className="label-caps">Estado del envío</p>
          <h2 className="mt-1 text-lg font-semibold">
            {doc.status === "registrado"
              ? "Registrado en el sistema empresarial"
              : doc.status === "formulario_completado"
                ? "Formulario completado — revise antes de guardar"
                : "Datos enviados, esperando procesamiento…"}
          </h2>
          <p className="mt-1.5 text-sm text-muted-foreground">
            {doc.status === "formulario_completado"
              ? "Revise el Reporte de Control de Datos con el contribuyente y luego pulse Grabar en RUAT. El agente no guardó el trámite."
              : "El agente de escritorio recibirá los datos y completará el formulario en Firefox."}
          </p>
          {doc.error_message ? (
            <p className="mt-3 flex items-start gap-2 rounded-xl bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {doc.error_message}
            </p>
          ) : null}
        </div>
      ) : revisar.length > 0 ? (
        <div className="mb-4 flex items-start gap-2.5 rounded-xl border border-warning/40 bg-warning/15 px-4 py-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning-foreground" />
          <p className="text-sm text-warning-foreground">
            <strong className="font-semibold">Datos que requieren revisión:</strong>{" "}
            {revisar.map((c) => c.label).join(", ")}
          </p>
        </div>
      ) : null}

      <section className="panel mb-4 overflow-hidden">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <p className="label-caps flex items-center gap-1.5">
            <UserRound className="h-3.5 w-3.5" /> Fotografía para RUAT
          </p>
          {doc.foto_path ? (
            <span className="text-[11px] font-medium text-success">Lista (≤ 90 KB)</span>
          ) : (
            <span className="text-[11px] font-medium text-destructive">Falta captura</span>
          )}
        </div>

        {camaraActiva && !bloqueado ? (
          <div className="p-3">
            <div className="ink-panel relative overflow-hidden">
              <video ref={videoRef} playsInline muted className="aspect-square w-full object-cover" />
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-6">
                <div className="h-[70%] w-[70%] rounded-full border-2 border-dashed border-primary-foreground/50" />
              </div>
              {camaraEstado === "iniciando" ? (
                <div className="absolute inset-0 flex items-center justify-center bg-ink/70">
                  <Loader2 className="h-6 w-6 animate-spin text-primary-foreground" />
                </div>
              ) : null}
            </div>
            <canvas ref={canvasRef} className="hidden" />
            <p className="mt-2 text-center text-xs text-muted-foreground">
              Cámara trasera · encuadre el rostro en el círculo
            </p>
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                disabled={camaraEstado !== "listo" || capturandoFoto}
                onClick={() => void guardarFotoDesdeCamara()}
                className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground disabled:opacity-60"
              >
                {capturandoFoto ? <Loader2 className="h-4 w-4 animate-spin" /> : <Camera className="h-4 w-4" />}
                Capturar foto
              </button>
              <button
                type="button"
                disabled={capturandoFoto}
                onClick={detenerCamara}
                className="rounded-xl border border-border px-4 py-3 text-sm font-medium"
              >
                Cancelar
              </button>
            </div>
          </div>
        ) : fotoUrl ? (
          <div className="px-4 py-3">
            <img src={fotoUrl} alt="Fotografía del contribuyente" className="mx-auto max-h-48 object-contain" />
            {!bloqueado ? (
              <button
                type="button"
                onClick={() => void abrirCamaraFoto()}
                className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl border border-border px-4 py-2.5 text-sm font-medium"
              >
                <Camera className="h-4 w-4" /> Cambiar fotografía
              </button>
            ) : null}
          </div>
        ) : (
          <div className="px-4 py-6 text-center">
            <p className="text-sm text-muted-foreground">No hay fotografía todavía.</p>
            {!bloqueado ? (
              <button
                type="button"
                onClick={() => void abrirCamaraFoto()}
                className="mt-3 inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground"
              >
                <Camera className="h-4 w-4" /> Añadir fotografía
              </button>
            ) : null}
          </div>
        )}
      </section>

      <section className="panel divide-y divide-border">
        {CAMPOS.map((campo) => {
          const tono = confianzaTone(confianza[campo.key]);
          return (
            <div key={campo.key} className="px-4 py-3.5">
              <div className="flex items-center justify-between gap-2">
                <span className="label-caps">{campo.label}</span>
                <span
                  className={`flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-medium ${TONE_CLASS[tono]}`}
                >
                  {tono === "ok" ? <Check className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
                  {Math.round((confianza[campo.key] ?? 0) * 100)}%
                </span>
              </div>
              {campo.type === "select" ? (
                <select
                  disabled={bloqueado}
                  value={valores[campo.key] ?? ""}
                  onChange={(e) => setValores((v) => ({ ...v, [campo.key]: e.target.value }))}
                  className="mt-1.5 w-full rounded-xl border border-input bg-background px-3.5 py-2.5 text-sm outline-none focus:border-primary disabled:opacity-70"
                >
                  <option value="">Seleccione…</option>
                  {campo.options.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  disabled={bloqueado}
                  value={valores[campo.key] ?? ""}
                  maxLength={120}
                  onChange={(e) => setValores((v) => ({ ...v, [campo.key]: e.target.value }))}
                  className="mt-1.5 w-full rounded-xl border border-input bg-background px-3.5 py-2.5 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-ring/25 disabled:opacity-70"
                />
              )}
            </div>
          );
        })}
      </section>

      {!bloqueado ? (
        <>
          <div className="mt-4 space-y-2.5">
            <button
              onClick={() => void confirmar()}
              disabled={guardando || !doc.foto_path}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3.5 text-sm font-semibold text-primary-foreground disabled:opacity-60"
            >
              {guardando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Confirmar datos y enviar al PC
            </button>
            <div className="flex gap-2.5">
              <button
                onClick={() => router.navigate({ to: "/escanear" })}
                className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-border bg-surface px-4 py-3 text-sm font-medium"
              >
                <RotateCcw className="h-4 w-4" /> Volver a escanear
              </button>
              <button
                onClick={() => void cancelar()}
                className="flex items-center justify-center gap-2 rounded-xl border border-border px-4 py-3 text-sm font-medium text-destructive"
              >
                <X className="h-4 w-4" /> Cancelar
              </button>
            </div>
          </div>
        </>
      ) : (
        <button
          onClick={() => router.navigate({ to: "/inicio" })}
          className="mt-4 w-full rounded-xl border border-border bg-surface px-4 py-3 text-sm font-medium"
        >
          Volver al inicio
        </button>
      )}
    </AppShell>
  );
}
