import { useEffect, useState } from "react";
import { Wifi, WifiOff } from "lucide-react";

export function ConnectionBadge() {
  const [online, setOnline] = useState(true);

  useEffect(() => {
    const actualizar = () => setOnline(navigator.onLine);
    actualizar();
    window.addEventListener("online", actualizar);
    window.addEventListener("offline", actualizar);
    return () => {
      window.removeEventListener("online", actualizar);
      window.removeEventListener("offline", actualizar);
    };
  }, []);

  return (
    <span
      title={online ? "Conectado" : "Sin conexión"}
      className={`flex items-center gap-1.5 rounded-lg border px-2 py-1.5 text-[11px] font-medium ${
        online ? "border-success/30 bg-success/10 text-success" : "border-destructive/30 bg-destructive/10 text-destructive"
      }`}
    >
      {online ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
      <span className="hidden sm:inline">{online ? "En línea" : "Sin red"}</span>
    </span>
  );
}