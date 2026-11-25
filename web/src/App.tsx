import React from "react";
import { RouterProvider } from "@tanstack/react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { router } from "./router";
import { AuthProvider } from "./context/AuthContext";
import { UiProvider } from "./ui";

const queryClient = new QueryClient();

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
