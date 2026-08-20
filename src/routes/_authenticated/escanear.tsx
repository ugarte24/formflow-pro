import { createFileRoute, useRouter } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { useServerFn } from "@tanstack/react-start";
import { AlertTriangle, Camera, Check, Loader2, Sun, Focus, UserRound } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { supabase } from "@/integrations/supabase/client";
import { extraerDatosDocumento } from "@/lib/ocr.functions";
import { canvasToJpegUnderLimit } from "@/lib/image-compress";
import { useSesion } from "@/hooks/useSesion";

export const Route = createFileRoute("/_authenticated/escanear")({
  head: () => ({
    meta: [
      { title: "Escanear documento — Digitalizador" },
      {
        name: "description",
        content: "Captura el documento de identidad y la fotografía del contribuyente.",
      },
      { property: "og:title", content: "Escanear documento — Digitalizador" },
      { property: "og:description", content: "Captura el CI y la foto para el registro RUAT." },
    ],
  }),
  component: Escanear,
});

type Calidad = { nitidez: number; luz: number; ok: boolean };
type Fase = "ci" | "foto";

function Escanear() {
  const router = useRouter();
  const { data: sesion } = useSesion();
  const extraer = useServerFn(extraerDatosDocumento);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [fase, setFase] = useState<Fase>("ci");
  const [docId, setDocId] = useState<string | null>(null);
  const [estado, setEstado] = useState<"iniciando" | "listo" | "procesando" | "error">("iniciando");
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [calidad, setCalidad] = useState<Calidad>({ nitidez: 0, luz: 0, ok: false });
  const [paso, setPaso] = useState("");
  /** Frame congelado del CI (solo vista; no se sube a Storage). */
  const [previewCi, setPreviewCi] = useState<string | null>(null);

  const detener = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const iniciarCamara = useCallback(
    async (facing: "environment" | "user") => {
      detener();
      setEstado("iniciando");
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: facing }, width: { ideal: 1920 } },
          audio: false,
        });
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
    },
    [detener],
  );

  useEffect(() => {
    // Siempre camara trasera: CI y fotografia del contribuyente
    setPreviewCi(null);
    void iniciarCamara("environment");
    return () => detener();
  }, [fase, iniciarCamara, detener]);

  const medirCalidad = useCallback(() => {
    if (previewCi) return;
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
  }, [previewCi]);

  useEffect(() => {
    if (estado !== "listo" || fase !== "ci" || previewCi) return;
    const id = window.setInterval(() => {
      medirCalidad();
    }, 450);
    return () => window.clearInterval(id);
  }, [estado, medirCalidad, fase, previewCi]);

  async function dibujarFrame(): Promise<HTMLCanvasElement> {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) throw new Error("Cámara no lista");
    const ancho = Math.min(1600, video.videoWidth || 1280);
    const alto = Math.round((ancho / (video.videoWidth || 1)) * (video.videoHeight || 720));
    canvas.width = ancho;
    canvas.height = alto;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("No se pudo procesar la imagen");
    ctx.drawImage(video, 0, 0, ancho, alto);
    return canvas;
  }

  async function capturarCi() {
    if (!sesion || estado === "procesando") return;
    setEstado("procesando");
    setMensaje(null);
    try {
      // Congelar al instante: ya no hace falta seguir enfocando
      const canvas = await dibujarFrame();
      const dataUrl = canvas.toDataURL("image/jpeg", 0.88);
      setPreviewCi(dataUrl);
      const base64 = dataUrl.split(",")[1] ?? "";

      setPaso("Leyendo el documento…");
      const { data: doc, error: insErr } = await supabase
        .from("documents")
        .insert({
          operator_id: sesion.userId,
          image_path: null,
          status: "procesando",
        })
        .select("id")
        .single();
      if (insErr) throw insErr;

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
        detalle: `Calidad: ${resultado.calidadImagen} · ${resultado.processingMs} ms · CI no guardado`,
      });

      setDocId(doc.id);
      setPreviewCi(null);
      setFase("foto");
      toast.success("Documento leído. Ahora capture la fotografía.");
    } catch (error) {
      setPreviewCi(null);
      setEstado("listo");
      const texto = error instanceof Error ? error.message : "No se pudo procesar la captura";
      setMensaje(texto);
      toast.error(texto);
    } finally {
      setPaso("");
    }
  }

  async function capturarFoto() {
    if (!sesion || !docId || estado === "procesando") return;
    setEstado("procesando");
    setMensaje(null);
    try {
      setPaso("Comprimiendo fotografía (máx. 90 KB)…");
      const canvas = await dibujarFrame();
      const { blob, bytes } = await canvasToJpegUnderLimit(canvas, 90 * 1024);

      setPaso("Guardando fotografía…");
      const nombre = `${sesion.userId}/${Date.now()}-foto.jpg`;
      const { error: upErr } = await supabase.storage.from("documentos").upload(nombre, blob, {
        contentType: "image/jpeg",
      });
      if (upErr) throw upErr;

      const { error: updErr } = await supabase
        .from("documents")
        .update({ foto_path: nombre })
        .eq("id", docId);
      if (updErr) throw updErr;

      await supabase.from("operation_logs").insert({
        document_id: docId,
        operator_id: sesion.userId,
        evento: "Fotografía capturada",
        detalle: `${bytes} bytes`,
      });

      detener();
      toast.success(`Fotografía lista (${Math.round(bytes / 1024)} KB)`);
      router.navigate({ to: "/verificar/$id", params: { id: docId } });
    } catch (error) {
      setEstado("listo");
      const texto = error instanceof Error ? error.message : "No se pudo guardar la fotografía";
      setMensaje(texto);
      toast.error(texto);
    } finally {
      setPaso("");
    }
  }

  async function capturar() {
    if (fase === "ci") await capturarCi();
    else await capturarFoto();
  }

  const titulo = fase === "ci" ? "1/2 · Documento de identidad" : "2/2 · Fotografía";
  const subtitulo =
    fase === "ci"
      ? "Coloque el documento dentro del marco"
      : "Use la cámara trasera y capture el rostro del contribuyente (≤ 90 KB)";

  return (
    <AppShell titulo={titulo} subtitulo={subtitulo} esAdmin={sesion?.esAdmin} fill>
      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden">
        <div className="ink-panel relative min-h-0 w-full flex-1 overflow-hidden">
          <video
            ref={videoRef}
            playsInline
            muted
            autoPlay
            className={`absolute inset-0 h-full w-full object-cover ${previewCi ? "invisible" : ""}`}
          />
          {previewCi ? (
            <img
              src={previewCi}
              alt="Documento capturado"
              className="absolute inset-0 h-full w-full object-cover"
            />
          ) : null}
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-4 sm:p-5">
            <div
              className={`border-2 border-dashed transition-colors ${
                fase === "ci"
                  ? `h-[78%] w-[90%] max-w-lg rounded-xl ${
                      previewCi
                        ? "border-success"
                        : calidad.ok
                          ? "border-success"
                          : "border-primary-foreground/40"
                    }`
                  : "h-[70%] w-[70%] max-w-[320px] rounded-full border-primary-foreground/50"
              }`}
            />
          </div>

          {estado === "procesando" ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-ink/55 text-center">
              <Loader2 className="h-7 w-7 animate-spin text-primary-foreground" />
              <p className="text-sm font-medium text-primary-foreground">{paso || "Procesando…"}</p>
              {previewCi ? (
                <p className="max-w-xs px-4 text-xs text-primary-foreground/80">
                  Imagen congelada — ya puede bajar el documento
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
        <canvas ref={canvasRef} className="hidden" />

        <div className="panel shrink-0 p-3">
          {fase === "ci" ? (
            <div className="mb-3 flex flex-wrap gap-x-4 gap-y-1.5">
              <Chequeo
                icono={<Focus className="h-3.5 w-3.5" />}
                label="Nítida"
                ok={calidad.nitidez > 0.3}
                valor={calidad.nitidez}
              />
              <Chequeo
                icono={<Sun className="h-3.5 w-3.5" />}
                label="Luz"
                ok={calidad.luz > 0.25 && calidad.luz < 0.92}
                valor={calidad.luz}
              />
            </div>
          ) : (
            <p className="mb-3 text-xs text-muted-foreground">
              Cámara trasera al rostro · máx. 90 KB
            </p>
          )}

          {mensaje ? (
            <p className="mb-3 flex items-start gap-2 rounded-xl bg-warning/20 px-3 py-2 text-xs text-warning-foreground">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              {mensaje}
            </p>
          ) : null}

          <button
            onClick={() => void capturar()}
            disabled={estado !== "listo"}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground disabled:opacity-60"
          >
            {fase === "ci" ? <Camera className="h-4 w-4" /> : <UserRound className="h-4 w-4" />}
            {fase === "ci" ? "Capturar documento" : "Capturar fotografía"}
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
    <div className="flex min-w-0 flex-1 items-center gap-2">
      <span className={ok ? "text-success" : "text-muted-foreground"}>
        {ok ? <Check className="h-3.5 w-3.5" /> : icono}
      </span>
      <span className="shrink-0 text-xs">{label}</span>
      <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full transition-all ${ok ? "bg-success" : "bg-warning"}`}
          style={{ width: `${Math.round(Math.min(1, valor) * 100)}%` }}
        />
      </div>
    </div>
  );
}
