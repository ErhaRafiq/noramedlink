import type { AuthResponse, AuthUser } from "@/lib/types";

const TOKEN_KEY = "nora_medlink_token";
const USER_KEY = "nora_medlink_user";

export type StoredSession = {
  token: string;
  user: AuthUser;
};

export function saveSession(auth: AuthResponse) {
  if (typeof window === "undefined") {
    return;
  }
  localStorage.setItem(TOKEN_KEY, auth.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(auth.user));
  localStorage.setItem("userId", String(auth.user.id));
  localStorage.setItem("userRole", auth.user.role.toUpperCase());
  localStorage.setItem("userName", auth.user.full_name);
  localStorage.setItem("userEmail", auth.user.email);
}

export function getSession(): StoredSession | null {
  if (typeof window === "undefined") {
    return null;
  }

  const token = localStorage.getItem(TOKEN_KEY);
  const userJson = localStorage.getItem(USER_KEY);
  if (!token || !userJson) {
    return null;
  }

  try {
    return { token, user: JSON.parse(userJson) as AuthUser };
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
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem("userId");
  localStorage.removeItem("userRole");
  localStorage.removeItem("userName");
  localStorage.removeItem("userEmail");
}

export function dashboardPathForRole(role: AuthUser["role"]) {
  if (role === "admin") {
    return "/admin";
  }

  return role === "doctor" ? "/dashboard/doctor" : "/dashboard/patient";
}
