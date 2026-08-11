import { createFileRoute, useRouter } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { useServerFn } from "@tanstack/react-start";
import { AlertTriangle, Camera, Check, Loader2, RefreshCw, Sun, Focus } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { supabase } from "@/integrations/supabase/client";
import { extraerDatosDocumento } from "@/lib/ocr.functions";
import { useSesion } from "@/hooks/useSesion";

export const Route = createFileRoute("/_authenticated/escanear")({
  head: () => ({
    meta: [
      { title: "Escanear documento — Digitalizador" },
      { name: "description", content: "Captura guiada del documento de identidad con control de nitidez e iluminación." },
      { property: "og:title", content: "Escanear documento — Digitalizador" },
      { property: "og:description", content: "Captura el documento y extrae los datos automáticamente." },
    ],
  }),
  component: Escanear,
});

type Calidad = { nitidez: number; luz: number; ok: boolean };

function Escanear() {
  const router = useRouter();
  const { data: sesion } = useSesion();
  const extraer = useServerFn(extraerDatosDocumento);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const autoRef = useRef(0);

  const [estado, setEstado] = useState<"iniciando" | "listo" | "procesando" | "error">("iniciando");
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [calidad, setCalidad] = useState<Calidad>({ nitidez: 0, luz: 0, ok: false });
  const [autoCaptura, setAutoCaptura] = useState(true);
  const [paso, setPaso] = useState("");

  const detener = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => {
    let cancelado = false;
    async function iniciar() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 } },
          audio: false,
        });
        if (cancelado) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play().catch(() => undefined);
        }
        setEstado("listo");
      } catch {
        setEstado("error");
        setMensaje("No se pudo acceder a la cámara. Revise los permisos del navegador.");
      }
    }
    iniciar();
    return () => {
      cancelado = true;
      detener();
    };
  }, [detener]);

  const medirCalidad = useCallback(() => {
    const video = videoRef.current;
    if (!video || video.videoWidth === 0) return;
    const c = document.createElement("canvas");
    c.width = 160;
    c.height = 120;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, c.width, c.height);
    const { data } = ctx.getImageData(0, 0, c.width, c.height);
    const gris = new Float32Array(c.width * c.height);
    let suma = 0;
    for (let i = 0; i < gris.length; i++) {
      const g = (data[i * 4]! * 0.299 + data[i * 4 + 1]! * 0.587 + data[i * 4 + 2]! * 0.114) / 255;
      gris[i] = g;
      suma += g;
    }
    const luz = suma / gris.length;
    let varianza = 0;
    let n = 0;
    for (let y = 1; y < c.height - 1; y++) {
      for (let x = 1; x < c.width - 1; x++) {
        const i = y * c.width + x;
        const lap =
          4 * gris[i]! - gris[i - 1]! - gris[i + 1]! - gris[i - c.width]! - gris[i + c.width]!;
        varianza += lap * lap;
        n++;
      }
    }
    const nitidez = Math.min(1, (varianza / n) * 45);
    const ok = nitidez > 0.3 && luz > 0.25 && luz < 0.92;
    setCalidad({ nitidez, luz, ok });
    return ok;
  }, []);

  useEffect(() => {
    if (estado !== "listo") return;
    const id = window.setInterval(() => {
      const ok = medirCalidad();
      if (ok && autoCaptura) {
        autoRef.current += 1;
        if (autoRef.current >= 3) {
          autoRef.current = 0;
          void capturar();
        }
      } else {
        autoRef.current = 0;
      }
    }, 450);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [estado, autoCaptura, medirCalidad]);

  async function capturar() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !sesion || estado === "procesando") return;

    setEstado("procesando");
    setMensaje(null);
    try {
      setPaso("Preparando imagen…");
      const ancho = Math.min(1600, video.videoWidth);
      const alto = Math.round((ancho / video.videoWidth) * video.videoHeight);
      canvas.width = ancho;
      canvas.height = alto;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("No se pudo procesar la imagen");
      ctx.drawImage(video, 0, 0, ancho, alto);
      const dataUrl = canvas.toDataURL("image/jpeg", 0.88);
      const base64 = dataUrl.split(",")[1] ?? "";
      const blob = await (await fetch(dataUrl)).blob();

      setPaso("Guardando captura…");
      const nombre = `${sesion.userId}/${Date.now()}.jpg`;
      const { error: upErr } = await supabase.storage.from("documentos").upload(nombre, blob, {
        contentType: "image/jpeg",
      });
      if (upErr) throw upErr;

      const { data: doc, error: insErr } = await supabase
        .from("documents")
        .insert({ operator_id: sesion.userId, image_path: nombre, status: "procesando" })
        .select("id")
        .single();
      if (insErr) throw insErr;

      setPaso("Leyendo el documento…");
      const resultado = await extraer({ data: { imageBase64: base64, mimeType: "image/jpeg" } });

      const bajaConfianza = Object.values(resultado.confianza).some((v) => v < 0.85);
      await supabase
        .from("documents")
        .update({
          ...resultado.campos,
          confianza: resultado.confianza,
          processing_ms: resultado.processingMs,
          status: bajaConfianza ? "pendiente_revision" : "datos_extraidos",
        })
        .eq("id", doc.id);

      await supabase.from("operation_logs").insert({
        document_id: doc.id,
        operator_id: sesion.userId,
        evento: "OCR completado",
        detalle: `Calidad: ${resultado.calidadImagen} · ${resultado.processingMs} ms`,
      });

      detener();
      router.navigate({ to: "/verificar/$id", params: { id: doc.id } });
    } catch (error) {
      setEstado("listo");
      const texto = error instanceof Error ? error.message : "No se pudo procesar la captura";
      setMensaje(texto);
      toast.error(texto);
    } finally {
      setPaso("");
    }
  }

  return (
    <AppShell titulo="Escanear documento" subtitulo="Coloque el documento dentro del marco" esAdmin={sesion?.esAdmin}>
      <div className="ink-panel relative overflow-hidden">
        <video
          ref={videoRef}
          playsInline
          muted
          className="aspect-[3/4] w-full object-cover sm:aspect-[4/3]"
        />
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-6">
          <div
            className={`h-[58%] w-full rounded-xl border-2 border-dashed transition-colors ${
              calidad.ok ? "border-success" : "border-primary-foreground/40"
            }`}
          />
        </div>

        {estado === "procesando" ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-ink/80 text-center">
            <Loader2 className="h-7 w-7 animate-spin text-primary-foreground" />
            <p className="text-sm font-medium text-primary-foreground">{paso || "Procesando…"}</p>
          </div>
        ) : null}
      </div>
      <canvas ref={canvasRef} className="hidden" />

      <div className="panel mt-4 p-4">
        <p className="label-caps">Validaciones en vivo</p>
        <div className="mt-3 space-y-2.5">
          <Chequeo
            icono={<Focus className="h-4 w-4" />}
            label="Imagen nítida"
            ok={calidad.nitidez > 0.3}
            valor={calidad.nitidez}
          />
          <Chequeo
            icono={<Sun className="h-4 w-4" />}
            label="Iluminación suficiente"
            ok={calidad.luz > 0.25 && calidad.luz < 0.92}
            valor={calidad.luz}
          />
        </div>

        <label className="mt-4 flex items-center justify-between rounded-xl border border-border bg-background px-3.5 py-3">
          <span className="text-sm font-medium">Captura automática</span>
          <input
            type="checkbox"
            checked={autoCaptura}
            onChange={(e) => setAutoCaptura(e.target.checked)}
            className="h-4 w-4 accent-primary"
          />
        </label>

        {mensaje ? (
          <p className="mt-3 flex items-start gap-2 rounded-xl bg-warning/20 px-3 py-2.5 text-xs text-warning-foreground">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            {mensaje}
          </p>
        ) : null}

        <div className="mt-4 flex gap-2">
          <button
            onClick={() => void capturar()}
            disabled={estado !== "listo"}
            className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground disabled:opacity-60"
          >
            <Camera className="h-4 w-4" /> Capturar ahora
          </button>
          <button
            onClick={() => router.navigate({ to: "/inicio" })}
            className="rounded-xl border border-border px-4 py-3 text-sm font-medium"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>
    </AppShell>
  );
}

function Chequeo({
  icono,
  label,
  ok,
  valor,
}: {
  icono: React.ReactNode;
  label: string;
  ok: boolean;
  valor: number;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className={ok ? "text-success" : "text-muted-foreground"}>{ok ? <Check className="h-4 w-4" /> : icono}</span>
      <span className="flex-1 text-sm">{label}</span>
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full transition-all ${ok ? "bg-success" : "bg-warning"}`}
          style={{ width: `${Math.round(Math.min(1, valor) * 100)}%` }}
        />
      </div>
    </div>
  );
}