// dependency-cruiser configuration template (Web/TS Architecture-Contract Gate).
// Copy to project root. The arch_contract_web.py gate runs:
//   depcruise --config .dependency-cruiser.cjs --output-type json <src>
// Docs: https://github.com/sverweij/dependency-cruiser
//
// NEUTRAL BY DEFAULT: the universal no-circular rule stays ACTIVE (structural);
// the example layer-boundary rule is COMMENTED OUT so a freshly-armed project has
// a GREEN gate. Uncomment + edit the layer rule to enforce YOUR boundaries.

/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    { name: "no-circular", severity: "error", comment: "circular dependency", from: {}, to: { circular: true } },
    // --- Uncomment + edit to enforce YOUR layer boundaries --------------------
    // {
    //   name: "no-outer-from-core",
    //   severity: "error",
    //   comment: "core must not depend on ui/server layers",
    //   from: { path: "^src/core/" },
    //   to: { path: "^src/(ui|server|pages)/" },
    // },
  ],
  options: {
    doNotFollow: { path: "node_modules" },
    tsPreCompilationDeps: true,
    enhancedResolveOptions: { extensions: [".ts", ".tsx", ".d.ts", ".js", ".jsx", ".mjs", ".cjs", ".json"], exportsFields: ["exports"], conditionNames: ["import", "require", "node"] },
  },
};
