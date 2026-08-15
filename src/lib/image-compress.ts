/** Comprime un canvas a JPEG por debajo de maxBytes (por defecto 90 KB para RUAT). */
export async function canvasToJpegUnderLimit(
  source: HTMLCanvasElement,
  maxBytes = 90 * 1024,
): Promise<{ blob: Blob; dataUrl: string; bytes: number }> {
  let quality = 0.85;
  let width = source.width;
  let height = source.height;

  for (let intento = 0; intento < 12; intento++) {
    const c = document.createElement("canvas");
    c.width = width;
    c.height = height;
    const ctx = c.getContext("2d");
    if (!ctx) throw new Error("No se pudo comprimir la imagen");
    ctx.drawImage(source, 0, 0, width, height);

    const dataUrl = c.toDataURL("image/jpeg", quality);
    const blob = await (await fetch(dataUrl)).blob();
    if (blob.size <= maxBytes) {
      return { blob, dataUrl, bytes: blob.size };
    }

    if (quality > 0.45) {
      quality -= 0.1;
    } else {
      width = Math.round(width * 0.85);
      height = Math.round(height * 0.85);
      quality = 0.75;
    }
  }

  const dataUrl = source.toDataURL("image/jpeg", 0.4);
  const blob = await (await fetch(dataUrl)).blob();
  return { blob, dataUrl, bytes: blob.size };
}
