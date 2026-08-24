import { useId } from "react";

export function GridField({
  label,
  value,
  type = "text",
  min,
  max,
  step,
  placeholder,
  onChange,
}: {
  label: string;
  value: string | number | undefined;
  type?: string;
  min?: number | string;
  max?: number | string;
  step?: number | string;
  placeholder?: string;
  onChange: (v: string) => void;
}) {
  const id = useId();
  return (
    <div className="form-field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type={type}
        min={min}
        max={max}
        step={step}
        placeholder={placeholder}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
