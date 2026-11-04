// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { useId, type HTMLAttributes } from "react";

export function GridField({
  label,
  value,
  type = "text",
  min,
  max,
  step,
  inputMode,
  placeholder,
  onChange,
}: {
  label: string;
  value: string | number | undefined;
  type?: string;
  min?: number | string;
  max?: number | string;
  step?: number | string;
  inputMode?: HTMLAttributes<HTMLInputElement>["inputMode"];
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
        inputMode={inputMode}
        placeholder={placeholder}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
