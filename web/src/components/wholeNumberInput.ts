// Attributes for every odometer / engine-hours input (Vikunja #342): whole
// numbers only, the same rule as the mobile apps. The backend stores these
// as integers and rejects a fractional value outright, so an input with
// step="0.1" let someone type "12345.6" and then the whole save failed.
// step=1 makes the browser's own form validation stop a decimal at submit,
// with its standard message, before any request is sent. Spread onto an
// <input> or a <GridField>.
export const WHOLE_NUMBER_INPUT = {
  type: "number",
  step: 1,
  min: 0,
  inputMode: "numeric",
} as const;
