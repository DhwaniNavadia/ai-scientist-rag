import { cn } from "@/lib/utils";

type Status = "idle" | "running" | "completed" | "error" | "pending";

const config: Record<Status, { label: string; classes: string; dot?: string }> = {
  idle: {
    label: "Idle",
    classes: "bg-secondary text-secondary-foreground",
  },
  pending: {
    label: "Pending",
    classes: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
    dot: "bg-blue-500",
  },
  running: {
    label: "Running",
    classes:
      "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300",
    dot: "bg-yellow-500 animate-pulse",
  },
  completed: {
    label: "Completed",
    classes: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
    dot: "bg-green-500",
  },
  error: {
    label: "Error",
    classes: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
    dot: "bg-red-500",
  },
};

interface StatusBadgeProps {
  status: Status;
  label?: string;
  className?: string;
}

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  const cfg = config[status] ?? config.idle;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        cfg.classes,
        className
      )}
    >
      {cfg.dot && <span className={cn("h-1.5 w-1.5 rounded-full", cfg.dot)} />}
      {label ?? cfg.label}
    </span>
  );
}
