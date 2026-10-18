// MYELIN Emboss preset만 쓴다 (ADR-0007, ADR-0008).
// 기본 팔레트·그림자를 비워서 토큰 밖의 색(`bg-red-500` 등)은 클래스 자체가 생성되지 않게 한다.
const emboss = require("../../../design/dist/tailwind.preset.js");

/** @type {import('tailwindcss').Config} */
module.exports = {
  presets: [emboss],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    colors: { transparent: "transparent", current: "currentColor", inherit: "inherit" },
    boxShadow: { none: "none" },
  },
};
