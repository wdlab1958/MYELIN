/* Emboss preset only — every color/shadow/radius is a CSS variable generated from design/tokens.json. */
const preset = require("../../../design/dist/tailwind.preset.cjs");
module.exports = {
  presets: [preset],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  corePlugins: { preflight: true },
};
