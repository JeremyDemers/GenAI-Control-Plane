import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./features/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172033",
        panel: "#f7f8fb",
        line: "#d8dee8",
        mint: "#1f8f75",
        amber: "#b66a00",
        coral: "#be4b49"
      },
      boxShadow: {
        quiet: "0 1px 2px rgba(23,32,51,0.08)"
      }
    }
  },
  plugins: []
};

export default config;

