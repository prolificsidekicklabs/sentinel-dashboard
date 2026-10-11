const nextJest = require("next/jest");

const createJestConfig = nextJest({ dir: "./" });

module.exports = createJestConfig({
  clearMocks: true,
  testEnvironment: "node",
  testPathIgnorePatterns: ["/node_modules/", "/.next/", "/backend/"],
});
