interface ProgressBarProps {
  percent: number;
  className?: string;
}

export default function ProgressBar({ percent, className }: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, percent));
  const color = clamped >= 100 ? "bg-green-500" : clamped > 50 ? "bg-brand-500" : "bg-blue-500";

  return (
    <div className={`w-full bg-zinc-800 rounded-full h-1.5 overflow-hidden ${className || ""}`}>
      <div
        className={`h-full rounded-full transition-all duration-300 ${color}`}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
