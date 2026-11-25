import React from "react";
import { RouterProvider } from "@tanstack/react-router";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "./api/apiCache";
import { router } from "./router";
import { AuthProvider } from "./context/AuthContext";
import { UiProvider } from "./ui";

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <UiProvider>
          <RouterProvider router={router} />
        </UiProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
};
