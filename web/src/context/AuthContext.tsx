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

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(() => {
    const saved = localStorage.getItem("fwt_user");
    return saved ? JSON.parse(saved) : null;
  });
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("fwt_token"));

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

