import { api, isApiError } from "@/lib/api";
import type { AuthResponse, AuthUser } from "@/lib/types";

// Only the user's profile is kept in the browser, to draw the page. The session itself is an HttpOnly
// cookie that JavaScript cannot read (see lib/server-session.ts); there is no token here.
const USER_KEY = "nora_medlink_user";

/** Fired on window whenever this tab signs in or out (other tabs get the "storage" event). */
export const SESSION_CHANGE_EVENT = "nora-session-change";

function announceSessionChange() {
  window.dispatchEvent(new Event(SESSION_CHANGE_EVENT));
}

/** Raw stored profile as one string, for useSyncExternalStore snapshots ("" when signed out). */
export function readSessionSnapshot() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(USER_KEY) ?? "";
}

export type StoredSession = {
  user: AuthUser;
};

export function saveSession(auth: AuthResponse) {
  if (typeof window === "undefined") {
    return;
  }
  localStorage.setItem(USER_KEY, JSON.stringify(auth.user));
  localStorage.setItem("userId", String(auth.user.id));
  localStorage.setItem("userRole", auth.user.role.toUpperCase());
  localStorage.setItem("userName", auth.user.full_name);
  localStorage.setItem("userEmail", auth.user.email);
  announceSessionChange();
}

export function getSession(): StoredSession | null {
  if (typeof window === "undefined") {
    return null;
  }

  const userJson = localStorage.getItem(USER_KEY);
  if (!userJson) {
    return null;
  }

  try {
    return { user: JSON.parse(userJson) as AuthUser };
  } catch {
    clearSession();
    return null;
  }
}

export function updateStoredUser(user: AuthUser) {
  if (typeof window === "undefined") {
    return;
  }
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  localStorage.setItem("userId", String(user.id));
  localStorage.setItem("userRole", user.role.toUpperCase());
  localStorage.setItem("userName", user.full_name);
  localStorage.setItem("userEmail", user.email);
}

export function clearSession() {
  if (typeof window === "undefined") {
    return;
  }
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem("userId");
  localStorage.removeItem("userRole");
  localStorage.removeItem("userName");
  localStorage.removeItem("userEmail");
  announceSessionChange();
}

/**
 * Signs out: forgets the profile at once and ends the session on the server (which clears the cookies).
 * Callers go to the next page only after it resolves: the server clears the cookies in its answer, and a page
 * that checks the session (sign in) before that would still find it valid and send the person back.
 * A slow or unreachable server does not hold the person up for more than a few seconds.
 */
export async function signOut() {
  clearSession();
  await Promise.race([api.logout().catch(() => undefined), new Promise((resolve) => setTimeout(resolve, 4000))]);
}

/** Pages that need a signed-in user (mirrored by proxy.ts, which sends visitors without a session cookie to /login). */
export const PROTECTED_PREFIXES = ["/dashboard", "/admin", "/profile", "/notifications", "/payments"];

export function isProtectedPath(path: string) {
  return PROTECTED_PREFIXES.some((prefix) => path === prefix || path.startsWith(`${prefix}/`));
}

/** A same-site path to return to after signing in; anything else (another site, "//host") is ignored. */
export function safeNextPath(value: string | null | undefined) {
  return value && value.startsWith("/") && !value.startsWith("//") && !value.startsWith("/\\") ? value : null;
}

export function loginUrl(next?: string, reason?: "expired") {
  const params = new URLSearchParams();
  if (reason) params.set(reason, "1");
  const safe = safeNextPath(next);
  if (safe && safe !== "/") params.set("next", safe);
  const query = params.toString();
  return query ? `/login?${query}` : "/login";
}

/**
 * Asks the server whether the cookie session still works (it renews an expired access token from the refresh
 * cookie). "lost" only on 401/403; an unreachable backend is "unknown" and keeps the session.
 */
export async function verifySession(signal?: AbortSignal): Promise<"ok" | "lost" | "unknown"> {
  try {
    const user = await api.me({ signal });
    updateStoredUser(user);
    return "ok";
  } catch (error) {
    if (isApiError(error, 401) || isApiError(error, 403)) return "lost";
    return "unknown";
  }
}

export function dashboardPathForRole(role: AuthUser["role"]) {
  if (role === "admin") {
    return "/admin";
  }

  return role === "doctor" ? "/dashboard/doctor" : "/dashboard/patient";
}
