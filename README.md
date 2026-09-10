# WASM WebGPU glTF Viewer

Renders a glTF file containing two boxes with a glowing cable between them, using WebGPU via WASM (Rust + wgpu).

![WebGPU](https://img.shields.io/badge/WebGPU-ready-blue) ![Rust](https://img.shields.io/badge/Rust-wgpu25-orange) ![WASM](https://img.shields.io/badge/WASM-wasm--pack-yellow)

## Features

- **Custom GLB parser** — reads the glTF binary format directly in Rust (no external glTF library)
- **Two render pipelines** — opaque Lambertian shading for boxes, additive blending for the glowing cable
- **Animated glow** — pulsing intensity + traveling wave along the cable's length
- **Multi-light shading** — key light (warm, specular), fill light (cool), ambient gradient, Fresnel rim
- **Orbiting camera** — smooth circular motion with vertical bob
- **162 KB WASM binary** — no JS dependencies, no bundler required

## Requirements

- **Browser**: Chrome/Edge 113+ with WebGPU enabled
- **Build**: Rust 1.75+, `wasm-pack`, `wasm32-unknown-unknown` target
- **Deploy**: IIS 10+ (Windows 10/11) or any static file server

## Build from source

```bash
# Install wasm-pack if needed
cargo install wasm-pack

# Generate the glTF asset
python3 generate_gltf.py

# Build the WASM module
wasm-pack build --target web --out-dir www/pkg
```

## Deploy on IIS (Windows 11)

### Option A: Copy files to IIS

1. Copy the entire `www/` folder to your IIS site root (e.g., `C:\inetpub\wwwroot\webgpu-gltf\`)
2. Ensure the folder contains:
   - `index.html`
   - `scene.glb`
   - `web.config` (sets correct MIME types for `.wasm` and `.glb`)
   - `pkg/` (contains `wasm_webgpu_gltf.js` and `wasm_webgpu_gltf_bg.wasm`)
3. In IIS Manager, add a new site or use Default Web Site, pointing to the folder
4. Open `http://localhost/webgpu-gltf/` in Chrome or Edge

### Option B: Use the included PowerShell script

```powershell
# Run as Administrator
.\deploy-iis.ps1
```

The script creates an IIS site called "WebGPU-gltf" on port 8080, copies the files, and opens the browser.

### `web.config` details

The included `web.config` does three things:

1. **MIME types**: Registers `.wasm` → `application/wasm` and `.glb` → `model/gltf-binary` (IIS doesn't know these by default and will 404 without them)
2. **JS MIME**: Ensures `.js` files are served as `application/javascript` (needed for ES module imports)
3. **CORS headers**: Sets `Cross-Origin-Opener-Policy` and `Cross-Origin-Embedder-Policy` for cross-origin isolation (required for WASM threads / SharedArrayBuffer if used in future)

## Run locally (any OS)

```bash
cd www
python3 -m http.server 8765
# Open http://localhost:8765 in Chrome/Edge
```

## Project structure

```
wasm-webgpu-gltf/
├── Cargo.toml           Rust package manifest (wgpu 25, wasm-bindgen)
├── generate_gltf.py     Generates www/scene.glb — 2 boxes + cylinder with emissive
├── src/
│   └── lib.rs           Rust WASM module: GLB parser, WebGPU renderer, WGSL shaders
├── www/                  Static site root (deploy this to IIS)
│   ├── index.html       Loads WASM, creates canvas, runs render loop
│   ├── scene.glb        The glTF binary asset (4.6 KB)
│   ├── web.config       IIS config: MIME types + CORS headers
│   └── pkg/             wasm-pack output (committed for IIS deploy)
│       ├── wasm_webgpu_gltf.js      JS glue (51 KB)
│       └── wasm_webgpu_gltf_bg.wasm  WASM binary (162 KB)
├── deploy-iis.ps1       PowerShell script for IIS deployment
└── README.md
```

## How the glow works

The cable uses a separate render pipeline with **additive blending** (`src=1, dst=1, op=add`) and **depth-write disabled** so the glow doesn't occlude itself. The fragment shader computes:

```wgsl
let pulse = 0.5 + 0.5 * sin(time * 2.0);                    // global brightness pulse
let wave = 0.5 + 0.5 * sin(time * 4.0 + pos.x * 5.0);       // traveling wave along cable
let intensity = (0.7 + pulse * 0.5) * (0.5 + wave * 0.5);
return vec4(vec3(0.05, 1.0, 0.4) * intensity, 1.0);
```

## License

MIT
