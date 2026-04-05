import { cn } from "@/lib/utils";

type Size = "sm" | "md" | "lg";

export function LoadingSpinner({ size = "md", className }: { size?: Size; className?: string }) {
  const sizeClasses: Record<Size, string> = {
    sm: "h-4 w-4 border-2",
    md: "h-6 w-6 border-2",
    lg: "h-10 w-10 border-4",
  };
  return (
    <span
      className={cn(
        "inline-block animate-spin rounded-full border-muted-foreground border-r-transparent",
        sizeClasses[size],
        className
      )}
      role="status"
      aria-label="Loading"
    />
  );
}
