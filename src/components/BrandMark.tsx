import { ScanLine } from "lucide-react";
import { cn } from "@/lib/utils";

/** Marca Digitalizador: ScanLine en cuadrado primary (mismo look que la home). */
export function BrandMark({ className, iconClassName }: { className?: string; iconClassName?: string }) {
  return (
    <span
      className={cn(
        "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground",
        className,
      )}
      aria-hidden
    >
      <ScanLine className={cn("h-5 w-5", iconClassName)} />
    </span>
  );
}
