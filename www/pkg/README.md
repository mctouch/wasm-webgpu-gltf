# WASM WebGPU glTF Viewer

Renders a glTF file containing two boxes with a glowing cable between them, using WebGPU via WASM (Rust + wgpu).

## Requirements

- Rust 1.75+ with `wasm32-unknown-unknown` target
- `wasm-pack` (`cargo install wasm-pack`)
- Chrome/Edge 113+ with WebGPU enabled

## Build

```bash
# Generate the glTF file
python3 generate_gltf.py

# Build the WASM module
wasm-pack build --target web --out-dir www/pkg
```

## Run

```bash
cd www
python3 -m http.server 8765
# Open http://localhost:8765 in Chrome/Edge
```

## Structure

- `generate_gltf.py` — generates `www/scene.glb`: two boxes at x=±2, a cylinder cable between them with emissive green material
- `src/lib.rs` — Rust WASM module: GLB parser, WebGPU renderer with two pipelines (opaque + additive glow)
- `www/index.html` — HTML page that loads the WASM module and renders to a canvas
- `www/scene.glb` — the generated glTF binary (4.6 KB)
- `www/pkg/` — wasm-pack output (JS + WASM)

## How it works

1. **GLB parsing**: The Rust code reads the GLB binary format (JSON + binary chunks), extracts mesh primitives (positions, normals, indices), and bakes node transforms (translation/scale) into vertex data at load time.

2. **Two render pipelines**:
   - **Opaque pipeline**: Renders non-emissive meshes (the two boxes) with basic Lambertian shading.
   - **Glow pipeline**: Renders emissive meshes (the cable) with additive blending and a pulsing animated glow shader. Depth writes are disabled so the glow doesn't occlude itself.

3. **Animated camera**: Orbits around the scene with a slight vertical bob.

4. **Glow effect**: The cable's fragment shader uses `sin(time * 2.0)` for pulsing intensity and `sin(time * 4.0 + world_pos.x * 5.0)` for a traveling wave pattern along the cable's length.
