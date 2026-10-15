import { api } from "@/lib/api";
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

/** Signs out: forgets the profile at once and ends the session on the server (which clears the cookies). */
export function signOut() {
  clearSession();
  return api.logout().catch(() => undefined);
}

export function dashboardPathForRole(role: AuthUser["role"]) {
  if (role === "admin") {
    return "/admin";
  }

  return role === "doctor" ? "/dashboard/doctor" : "/dashboard/patient";
}
