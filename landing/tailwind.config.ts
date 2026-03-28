import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        primary: "#00d4aa",
        dark: { 900: "#0a0a0a", 800: "#111111", 700: "#1a1a1a", 600: "#222222" },
        gem: { green: "#00d4aa", red: "#ff4444", yellow: "#ffaa00", blue: "#4488ff" },
      },
      fontFamily: { mono: ["JetBrains Mono", "Fira Code", "monospace"] },
    },
  },
  plugins: [],
};
export default config;
