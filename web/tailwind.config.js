/** Design tokens live in src/ui/tokens.css; these names map Tailwind classes onto them. */
const rgb = (name) => `rgb(var(${name}) / <alpha-value>)`;

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        fw: {
          bg: rgb("--fw-bg"),
          surface: rgb("--fw-surface"),
          muted: rgb("--fw-surface-muted"),
          border: rgb("--fw-border"),
          "border-strong": rgb("--fw-border-strong"),
          text: rgb("--fw-text"),
          "text-muted": rgb("--fw-text-muted"),
          "text-subtle": rgb("--fw-text-subtle"),
          overlay: rgb("--fw-overlay"),
          primary: rgb("--fw-primary"),
          "primary-hover": rgb("--fw-primary-hover"),
          "primary-soft": rgb("--fw-primary-soft"),
          "primary-text": rgb("--fw-primary-text"),
          focus: rgb("--fw-focus"),
          success: rgb("--fw-success"),
          "success-soft": rgb("--fw-success-soft"),
          "success-text": rgb("--fw-success-text"),
          warning: rgb("--fw-warning"),
          "warning-soft": rgb("--fw-warning-soft"),
          "warning-text": rgb("--fw-warning-text"),
          danger: rgb("--fw-danger"),
          "danger-hover": rgb("--fw-danger-hover"),
          "danger-soft": rgb("--fw-danger-soft"),
          "danger-text": rgb("--fw-danger-text"),
          info: rgb("--fw-info"),
          "info-soft": rgb("--fw-info-soft"),
          "info-text": rgb("--fw-info-text"),
        },
      },
      spacing: {
        "fw-1": "var(--fw-space-1)",
        "fw-2": "var(--fw-space-2)",
        "fw-3": "var(--fw-space-3)",
        "fw-4": "var(--fw-space-4)",
        "fw-5": "var(--fw-space-5)",
        "fw-6": "var(--fw-space-6)",
        "fw-7": "var(--fw-space-7)",
      },
      borderRadius: {
        "fw-sm": "var(--fw-radius-sm)",
        "fw-md": "var(--fw-radius-md)",
        "fw-lg": "var(--fw-radius-lg)",
        "fw-xl": "var(--fw-radius-xl)",
      },
      fontSize: {
        "fw-xs": ["var(--fw-text-xs)", { lineHeight: "1rem" }],
        "fw-sm": ["var(--fw-text-sm)", { lineHeight: "1.25rem" }],
        "fw-base": ["var(--fw-text-base)", { lineHeight: "1.25rem" }],
        "fw-lg": ["var(--fw-text-lg)", { lineHeight: "1.5rem" }],
        "fw-xl": ["var(--fw-text-xl)", { lineHeight: "1.75rem" }],
        "fw-2xl": ["var(--fw-text-2xl)", { lineHeight: "2rem" }],
      },
      boxShadow: {
        "fw-sm": "var(--fw-shadow-sm)",
        "fw-md": "var(--fw-shadow-md)",
        "fw-lg": "var(--fw-shadow-lg)",
      },
      zIndex: {
        "fw-modal": "var(--fw-z-modal)",
        "fw-popover": "var(--fw-z-popover)",
        "fw-toast": "var(--fw-z-toast)",
        "fw-tooltip": "var(--fw-z-tooltip)",
      },
    },
  },
  plugins: [],
};
