import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// tailwind-merge must know the token classes from tailwind.config.js; otherwise it reads
// `text-fw-sm` (a font size) as a colour and drops `text-fw-text` next to it.
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: ["fw-xs", "fw-sm", "fw-base", "fw-lg", "fw-xl", "fw-2xl"] }],
      rounded: [{ rounded: ["fw-sm", "fw-md", "fw-lg", "fw-xl"] }],
      shadow: [{ shadow: ["fw-sm", "fw-md", "fw-lg"] }],
      z: [{ z: ["fw-modal", "fw-popover", "fw-toast", "fw-tooltip"] }],
    },
  },
});

/** Join class names; later Tailwind classes win over earlier ones (`cn("px-2", "px-4")`). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
