import React, { createContext, useContext, useState, useEffect } from "react";

export interface UserProfile {
  id: string;
  employee_id: string;
  username: string;
  role: "ADMIN" | "ENGINEER" | "SUPERINTENDENT" | "SUPERVISOR" | "WORKER";
  is_active: boolean;
  must_change_password: boolean;
  version: number;
}

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  login: (username: string, password: string) => Promise<{ must_change_password: boolean }>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  logout: () => Promise<void>;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const API_BASE_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

// Global fetch interceptor for base URL routing and 401 Unauthorized responses
if (typeof window !== "undefined" && !(window as any).__fwt_fetch_interceptor_installed) {
  (window as any).__fwt_fetch_interceptor_installed = true;
  const originalFetch = window.fetch;
  window.fetch = async (...args) => {
    if (API_BASE_URL) {
      if (typeof args[0] === "string" && args[0].startsWith("/api/")) {
        args[0] = `${API_BASE_URL}${args[0]}`;
      } else if (args[0] instanceof Request && args[0].url.startsWith("/api/")) {
        args[0] = new Request(`${API_BASE_URL}${args[0].url}`, args[0]);
      }
    }
    const response = await originalFetch(...args);
    if (response.status === 401) {
      const url = typeof args[0] === "string" ? args[0] : (args[0] as Request).url;
      if (!url.includes("/auth/login")) {
        localStorage.removeItem("fwt_token");
        localStorage.removeItem("fwt_user");
        window.dispatchEvent(new CustomEvent("fwt:unauthorized"));
        if (window.location.pathname !== "/login") {
          window.location.href = "/login";
        }
      }
    }
    return response;
  };
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(() => {
    const saved = localStorage.getItem("fwt_user");
    return saved ? JSON.parse(saved) : null;
  });
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("fwt_token"));

  useEffect(() => {
    const handleUnauthorized = () => {
      setToken(null);
      setUser(null);
    };
    window.addEventListener("fwt:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("fwt:unauthorized", handleUnauthorized);
  }, []);

  useEffect(() => {
    if (user) {
      localStorage.setItem("fwt_user", JSON.stringify(user));
    } else {
      localStorage.removeItem("fwt_user");
    }
  }, [user]);

  useEffect(() => {
    if (token) {
      localStorage.setItem("fwt_token", token);
    } else {
      localStorage.removeItem("fwt_token");
    }
  }, [token]);

  const login = async (username: string, password: string) => {
    const res = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || "Login failed");
    }

    const data = await res.json();
    localStorage.setItem("fwt_token", data.access_token);
    localStorage.setItem("fwt_user", JSON.stringify(data.user));
    setToken(data.access_token);
    setUser(data.user);
    return { must_change_password: data.must_change_password };
  };

  const changePassword = async (currentPassword: string, newPassword: string) => {
    if (!token) throw new Error("Not authenticated");
    const res = await fetch("/api/v1/auth/change-password", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || "Password change failed");
    }

    const updatedUser = await res.json();
    setUser(updatedUser);
  };

  const logout = async () => {
    if (token) {
      await fetch("/api/v1/auth/logout", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {});
    }
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        login,
        changePassword,
        logout,
        isAuthenticated: !!token && !!user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

