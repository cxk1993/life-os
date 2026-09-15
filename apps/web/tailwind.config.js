/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    // 主题扩展由 T02 负责：它会把颜色挂在 CSS 变量上（var(--accent) 等），
    // 这里保持空，避免 T01 先把色板写死。
    extend: {},
  },
  plugins: [],
};
