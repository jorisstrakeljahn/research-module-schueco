"use client";

import { useTheme } from "next-themes";
import { Toaster as SonnerToaster } from "sonner";

export default function Toaster() {
  const { resolvedTheme } = useTheme();
  return (
    <SonnerToaster
      theme={resolvedTheme === "light" ? "light" : "dark"}
      position="top-right"
      richColors
    />
  );
}
