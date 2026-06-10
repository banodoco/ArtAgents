// component.tsx — resolved by the remotion adapter convention.
//
// The manifest (element.yaml) declares the capability contract:
//   - inputs/outputs with artifact_type (the semantic waist)
//   - params schema + defaults
//   - runtime: { adapter: remotion }
//
// The remotion adapter finds this file by path convention
// (<element-dir>/component.tsx). It is not declared in the manifest.
// If runtime.adapter is present, component.tsx is optional;
// without a declared adapter, it is required (defaults to remotion).
//
// See docs/contracts/capability-artifact-contract.md for the full
// capability/artifact contract.
export default function ExampleCard() {
  return null;
}
