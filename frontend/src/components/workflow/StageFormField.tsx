"use client";

import type { StageFieldConfig } from "@/types/workflow";

interface StageFormFieldProps {
  config: StageFieldConfig;
  value: unknown;
  onChange: (value: unknown) => void;
}

export default function StageFormField({ config, value, onChange }: StageFormFieldProps) {
  const baseInputClass =
    "w-full bg-zinc-900 border border-border rounded-md px-3 py-2.5 text-sm text-zinc-200 focus:outline-none focus:border-brand-500 transition-colors";

  const labelId = `field-${config.key}`;
  const stringValue = typeof value === "string" ? value : "";
  const numberValue = typeof value === "number" ? value : 0;
  const boolValue = !!value;

  return (
    <div className="space-y-2">
      <label htmlFor={labelId} className="block text-sm text-zinc-400">
        {config.label}
      </label>

      {config.type === "select" && (
        <select
          id={labelId}
          value={stringValue}
          onChange={(e) => onChange(e.target.value || null)}
          className={baseInputClass}
        >
          {config.options?.map((opt) => (
            <option key={String(opt.value)} value={String(opt.value)}>
              {opt.label}
            </option>
          ))}
        </select>
      )}

      {config.type === "text" && (
        <input
          id={labelId}
          type="text"
          value={stringValue}
          onChange={(e) => onChange(e.target.value || null)}
          placeholder={config.placeholder}
          className={baseInputClass}
        />
      )}

      {config.type === "textarea" && (
        <textarea
          id={labelId}
          value={stringValue}
          onChange={(e) => onChange(e.target.value || null)}
          placeholder={config.placeholder}
          rows={4}
          className={`${baseInputClass} resize-y`}
        />
      )}

      {config.type === "number" && (
        <input
          id={labelId}
          type="number"
          value={numberValue}
          onChange={(e) => onChange(e.target.value === "" ? 0 : Number(e.target.value))}
          min={config.min}
          max={config.max}
          step={config.step ?? 1}
          placeholder={config.placeholder}
          className={baseInputClass}
        />
      )}

      {config.type === "slider" && (
        <div className="flex items-center gap-3">
          <input
            id={labelId}
            type="range"
            min={config.min ?? 0}
            max={config.max ?? 100}
            step={config.step ?? 1}
            value={numberValue}
            onChange={(e) => onChange(Number(e.target.value))}
            className="flex-1 accent-brand-500"
          />
          <span className="text-sm text-zinc-300 w-12 text-right tabular-nums">
            {numberValue}
          </span>
        </div>
      )}

      {config.type === "checkbox" && (
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            id={labelId}
            type="checkbox"
            checked={boolValue}
            onChange={(e) => onChange(e.target.checked)}
            className="w-4 h-4 rounded border-border bg-zinc-900 text-brand-500 focus:ring-brand-500 focus:ring-offset-0"
          />
          <span className="text-sm text-zinc-300">{config.description || ""}</span>
        </label>
      )}

      {config.description && config.type !== "checkbox" && (
        <p className="text-xs text-zinc-500">{config.description}</p>
      )}
    </div>
  );
}
