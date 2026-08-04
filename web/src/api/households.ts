import { apiFetch } from "./client";
import type { Household } from "./types";

export function getCurrentHousehold(): Promise<Household> {
  return apiFetch("/households/me");
}
