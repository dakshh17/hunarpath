import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        saffron: {
          50: "#FFF7ED",
          100: "#FFEDD5",
          200: "#FED7AA",
          400: "#FB923C",
          500: "#E8752A",
          600: "#C45E1A",
          700: "#9A3412",
        },
        forest: {
          50: "#F0FDF4",
          100: "#DCFCE7",
          400: "#4ADE80",
          500: "#1B7A3D",
          600: "#145E2E",
          700: "#166534",
        },
        ivory: "#FFF8F0",
      },
      fontFamily: {
        sans: ['"Noto Sans"', "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
