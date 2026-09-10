use wasm_bindgen::prelude::*;
use wgpu::util::DeviceExt;

const SHADER: &str = r#"
struct Uniforms {
    view_proj: mat4x4<f32>,
    camera_pos: vec4<f32>,
    time: f32,
    _pad1: vec3<f32>,
    _pad2: f32,
};

@group(0) @binding(0) var<uniform> u: Uniforms;

struct VsIn {
    @location(0) pos: vec3<f32>,
    @location(1) nor: vec3<f32>,
};

struct VsOut {
    @builtin(position) clip_pos: vec4<f32>,
    @location(0) world_pos: vec3<f32>,
    @location(1) world_nor: vec3<f32>,
};

@vertex
fn vs_main(in: VsIn) -> VsOut {
    var out: VsOut;
    out.world_pos = in.pos;
    out.world_nor = normalize(in.nor);
    // Rust stores row-major; WGSL mat4x4 is column-major, so transpose
    let vp = transpose(u.view_proj);
    out.clip_pos = vp * vec4(in.pos, 1.0);
    return out;
}

@fragment
fn fs_main(in: VsOut) -> @location(0) vec4<f32> {
    let n = normalize(in.world_nor);
    let cam_dir = normalize(u.camera_pos.xyz - in.world_pos);

    // Key light (warm, upper-right-front)
    let key_dir = normalize(vec3(0.6, 0.7, 0.4));
    let key_diff = max(dot(n, key_dir), 0.0);
    let key_spec = pow(max(dot(reflect(-key_dir, n), cam_dir), 0.0), 32.0);

    // Fill light (cool, opposite side, softer)
    let fill_dir = normalize(vec3(-0.4, 0.2, 0.5));
    let fill_diff = max(dot(n, fill_dir), 0.0) * 0.35;

    // Ambient (sky-ish gradient based on normal.y)
    let ambient = mix(vec3(0.04, 0.04, 0.06), vec3(0.10, 0.11, 0.14), n.y * 0.5 + 0.5);

    let base = vec3(0.50, 0.56, 0.64);
    let key_color = vec3(1.0, 0.95, 0.88);
    let fill_color = vec3(0.55, 0.65, 1.0);

    var color = ambient * base;
    color += base * key_diff * key_color;
    color += base * fill_diff * fill_color;
    color += key_spec * key_color * 0.25;

    // Fresnel rim for depth perception
    let fresnel = pow(1.0 - max(dot(n, cam_dir), 0.0), 3.0);
    color += fresnel * vec3(0.08, 0.12, 0.20);

    return vec4(color, 1.0);
}

@fragment
fn fs_glow(in: VsOut) -> @location(0) vec4<f32> {
    let t = u.time;
    let pulse = 0.5 + 0.5 * sin(t * 2.0);
    let wave = 0.5 + 0.5 * sin(t * 4.0 + in.world_pos.x * 5.0);
    let glow = vec3(0.05, 1.0, 0.4);
    let intensity = (0.7 + pulse * 0.5) * (0.5 + wave * 0.5);
    return vec4(glow * intensity, 1.0);
}
"#;

#[repr(C)]
#[derive(Clone, Copy, bytemuck::Pod, bytemuck::Zeroable)]
struct Uniforms {
    view_proj: [[f32; 4]; 4],   // 64 bytes, offset 0
    camera_pos: [f32; 4],       // 16 bytes, offset 64
    time: f32,                  // 4 bytes, offset 80
    _pad1: [f32; 3],            // 12 bytes, offset 84
    _pad2: [f32; 4],            // 16 bytes, offset 96 -> total 112
}

struct Primitive {
    vertex_buf: wgpu::Buffer,
    index_buf: wgpu::Buffer,
    index_count: u32,
    is_emissive: bool,
}

#[wasm_bindgen]
pub struct Renderer {
    surface: wgpu::Surface<'static>,
    device: wgpu::Device,
    queue: wgpu::Queue,
    config: wgpu::SurfaceConfiguration,
    pipeline: wgpu::RenderPipeline,
    glow_pipeline: wgpu::RenderPipeline,
    uniform_buf: wgpu::Buffer,
    uniform_bgl: wgpu::BindGroupLayout,
    primitives: Vec<Primitive>,
    depth_texture: Option<wgpu::Texture>,
    start: f64,
}

fn mat4_mul(a: [[f32;4];4], b: [[f32;4];4]) -> [[f32;4];4] {
    let mut r = [[0f32;4];4];
    for i in 0..4 { for j in 0..4 {
        let mut s = 0f32;
        for k in 0..4 { s += a[i][k]*b[k][j]; }
        r[i][j] = s;
    }}
    r
}

fn perspective(fovy: f32, aspect: f32, zn: f32, zf: f32) -> [[f32;4];4] {
    let f = 1.0 / (fovy/2.0).tan();
    [
        [f/aspect, 0.0, 0.0, 0.0],
        [0.0, f, 0.0, 0.0],
        [0.0, 0.0, (zf+zn)/(zn-zf), (2.0*zf*zn)/(zn-zf)],
        [0.0, 0.0, -1.0, 0.0],
    ]
}

fn look_at(eye:[f32;3], ctr:[f32;3], up:[f32;3]) -> [[f32;4];4] {
    let f = norm3([ctr[0]-eye[0], ctr[1]-eye[1], ctr[2]-eye[2]]);
    let s = norm3(cross3(f, up));
    let u = cross3(s, f);
    [
        [s[0], s[1], s[2], -dot3(s,eye)],
        [u[0], u[1], u[2], -dot3(u,eye)],
        [-f[0], -f[1], -f[2], dot3(f,eye)],
        [0.0, 0.0, 0.0, 1.0],
    ]
}

fn norm3(v:[f32;3]) -> [f32;3] {
    let l = (v[0]*v[0]+v[1]*v[1]+v[2]*v[2]).sqrt();
    [v[0]/l, v[1]/l, v[2]/l]
}
fn dot3(a:[f32;3],b:[f32;3]) -> f32 { a[0]*b[0]+a[1]*b[1]+a[2]*b[2] }
fn cross3(a:[f32;3],b:[f32;3]) -> [f32;3] {
    [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
}

// --- Minimal GLB parser ---

fn parse_glb(data: &[u8]) -> (serde_json::Value, Vec<u8>) {
    let magic = u32::from_le_bytes([data[0],data[1],data[2],data[3]]);
    assert_eq!(magic, 0x46546C4, "not a GLB file");

    let mut pos = 12;
    let mut json: serde_json::Value = serde_json::Value::Null;
    let mut bin: Vec<u8> = Vec::new();

    while pos + 8 <= data.len() {
        let chunk_len = u32::from_le_bytes([data[pos],data[pos+1],data[pos+2],data[pos+3]]) as usize;
        let chunk_type = u32::from_le_bytes([data[pos+4],data[pos+5],data[pos+6],data[pos+7]]);
        let chunk_data = &data[pos+8..pos+8+chunk_len];

        if chunk_type == 0x4E4F534A {
            // Strip trailing null/whitespace padding from the JSON chunk
            let mut json_end = chunk_data.len();
            while json_end > 0 && chunk_data[json_end - 1] == 0 {
                json_end -= 1;
            }
            json = serde_json::from_slice(&chunk_data[..json_end])
                .unwrap_or(serde_json::Value::Null);
        } else if chunk_type == 0x004E4942 {
            bin = chunk_data.to_vec();
        }
        pos += 8 + chunk_len;
        while pos % 4 != 0 { pos += 1; }
    }

    (json, bin)
}

fn get_f32s(bin: &[u8], bv: &serde_json::Value, count: usize) -> Vec<[f32;3]> {
    let offset = bv["byteOffset"].as_u64().unwrap_or(0) as usize;
    let mut out = Vec::with_capacity(count);
    for i in 0..count {
        let base = offset + i * 12;
        let x = f32::from_le_bytes(bin[base..base+4].try_into().unwrap());
        let y = f32::from_le_bytes(bin[base+4..base+8].try_into().unwrap());
        let z = f32::from_le_bytes(bin[base+8..base+12].try_into().unwrap());
        out.push([x, y, z]);
    }
    out
}

fn get_u16s(bin: &[u8], bv: &serde_json::Value, count: usize) -> Vec<u16> {
    let offset = bv["byteOffset"].as_u64().unwrap_or(0) as usize;
    let mut out = Vec::with_capacity(count);
    for i in 0..count {
        let base = offset + i * 2;
        out.push(u16::from_le_bytes(bin[base..base+2].try_into().unwrap()));
    }
    out
}

#[wasm_bindgen]
impl Renderer {
    pub async fn init(canvas: web_sys::HtmlCanvasElement) -> Result<Renderer, JsValue> {
        let instance = wgpu::Instance::default();

        let surface = instance
            .create_surface(wgpu::SurfaceTarget::Canvas(canvas.clone()))
            .map_err(|e| JsValue::from_str(&format!("{:?}", e)))?;

        let adapter = instance
            .request_adapter(&wgpu::RequestAdapterOptions {
                power_preference: wgpu::PowerPreference::HighPerformance,
                ..Default::default()
            })
            .await
            .map_err(|e| JsValue::from_str(&format!("{:?}", e)))?;

        let (device, queue) = adapter
            .request_device(&wgpu::DeviceDescriptor {
                label: None,
                required_features: wgpu::Features::empty(),
                required_limits: wgpu::Limits::downlevel_webgl2_defaults(),
                memory_hints: wgpu::MemoryHints::default(),
                trace: wgpu::Trace::Off,
            })
            .await
            .map_err(|e| JsValue::from_str(&format!("{:?}", e)))?;

        let width = canvas.width().max(1);
        let height = canvas.height().max(1);
        let format = surface.get_capabilities(&adapter).formats[0];

        let config = wgpu::SurfaceConfiguration {
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            format,
            width,
            height,
            present_mode: wgpu::PresentMode::Fifo,
            desired_maximum_frame_latency: 2,
            alpha_mode: wgpu::CompositeAlphaMode::Auto,
            view_formats: vec![],
        };
        surface.configure(&device, &config);

        // Uniform buffer
        let uniform_buf = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("uniforms"),
            contents: bytemuck::bytes_of(&Uniforms {
                view_proj: [[0f32;4];4],
                camera_pos: [0f32;4],
                time: 0.0,
                _pad1: [0f32;3],
                _pad2: [0f32;4],
            }),
            usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
        });

        let uniform_bgl = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("u_bgl"),
            entries: &[wgpu::BindGroupLayoutEntry {
                binding: 0,
                visibility: wgpu::ShaderStages::VERTEX | wgpu::ShaderStages::FRAGMENT,
                ty: wgpu::BindingType::Buffer {
                    ty: wgpu::BufferBindingType::Uniform,
                    has_dynamic_offset: false,
                    min_binding_size: None,
                },
                count: None,
            }],
        });

        // Load GLB
        let glb_bytes = include_bytes!("../www/scene.glb");
        let (glb_json, glb_bin) = parse_glb(glb_bytes);

        let buffer_views = glb_json["bufferViews"].as_array().unwrap();
        let accessors = glb_json["accessors"].as_array().unwrap();
        let meshes = glb_json["meshes"].as_array().unwrap();
        let materials = glb_json["materials"].as_array().unwrap();
        let nodes = glb_json["nodes"].as_array().unwrap();

        // Build primitives with baked node transforms
        let mut primitives = Vec::new();

        for node in nodes {
            let mesh_idx = match node["mesh"].as_u64() {
                Some(idx) => idx as usize,
                None => continue,
            };

            let translation = node.get("translation")
                .and_then(|t| t.as_array())
                .map(|a| [
                    a[0].as_f64().unwrap_or(0.0) as f32,
                    a[1].as_f64().unwrap_or(0.0) as f32,
                    a[2].as_f64().unwrap_or(0.0) as f32,
                ]).unwrap_or([0.0, 0.0, 0.0]);

            let scale = node.get("scale")
                .and_then(|t| t.as_array())
                .map(|a| [
                    a[0].as_f64().unwrap_or(1.0) as f32,
                    a[1].as_f64().unwrap_or(1.0) as f32,
                    a[2].as_f64().unwrap_or(1.0) as f32,
                ]).unwrap_or([1.0, 1.0, 1.0]);

            let mesh = &meshes[mesh_idx];
            let prims = mesh["primitives"].as_array().unwrap();

            for prim in prims {
                let pos_acc = prim["attributes"]["POSITION"].as_u64().unwrap() as usize;
                let nor_acc = prim["attributes"]["NORMAL"].as_u64().unwrap() as usize;
                let idx_acc = prim["indices"].as_u64().unwrap() as usize;
                let mat_idx = prim["material"].as_u64().unwrap_or(0) as usize;

                let pos_count = accessors[pos_acc]["count"].as_u64().unwrap() as usize;
                let pos_bv = &buffer_views[accessors[pos_acc]["bufferView"].as_u64().unwrap() as usize];
                let nor_count = accessors[nor_acc]["count"].as_u64().unwrap() as usize;
                let nor_bv = &buffer_views[accessors[nor_acc]["bufferView"].as_u64().unwrap() as usize];
                let idx_count = accessors[idx_acc]["count"].as_u64().unwrap() as usize;
                let idx_bv = &buffer_views[accessors[idx_acc]["bufferView"].as_u64().unwrap() as usize];

                let positions = get_f32s(&glb_bin, pos_bv, pos_count);
                let normals = get_f32s(&glb_bin, nor_bv, nor_count);
                let indices = get_u16s(&glb_bin, idx_bv, idx_count);

                // Bake transform into vertices
                let mut vertex_data: Vec<f32> = Vec::with_capacity(pos_count * 6);
                for i in 0..pos_count {
                    let p = positions[i];
                    vertex_data.push(p[0] * scale[0] + translation[0]);
                    vertex_data.push(p[1] * scale[1] + translation[1]);
                    vertex_data.push(p[2] * scale[2] + translation[2]);
                    vertex_data.extend_from_slice(&normals[i]);
                }

                let vertex_buf = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
                    label: Some("vertices"),
                    contents: bytemuck::cast_slice(&vertex_data),
                    usage: wgpu::BufferUsages::VERTEX,
                });

                let index_buf = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
                    label: Some("indices"),
                    contents: bytemuck::cast_slice(&indices),
                    usage: wgpu::BufferUsages::INDEX,
                });

                let is_emissive = materials.get(mat_idx)
                    .and_then(|m| m.get("emissiveFactor"))
                    .is_some();

                primitives.push(Primitive {
                    vertex_buf,
                    index_buf,
                    index_count: idx_count as u32,
                    is_emissive,
                });
            }
        }

        // Shader
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("shader"),
            source: wgpu::ShaderSource::Wgsl(std::borrow::Cow::Borrowed(SHADER)),
        });

        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("layout"),
            bind_group_layouts: &[&uniform_bgl],
            push_constant_ranges: &[],
        });

        let vertex_state = wgpu::VertexState {
            module: &shader,
            entry_point: Some("vs_main"),
            compilation_options: Default::default(),
            buffers: &[wgpu::VertexBufferLayout {
                array_stride: 24,
                step_mode: wgpu::VertexStepMode::Vertex,
                attributes: &[
                    wgpu::VertexAttribute {
                        format: wgpu::VertexFormat::Float32x3,
                        offset: 0,
                        shader_location: 0,
                    },
                    wgpu::VertexAttribute {
                        format: wgpu::VertexFormat::Float32x3,
                        offset: 12,
                        shader_location: 1,
                    },
                ],
            }],
        };

        let depth_state = wgpu::DepthStencilState {
            format: wgpu::TextureFormat::Depth32Float,
            depth_write_enabled: true,
            depth_compare: wgpu::CompareFunction::Less,
            stencil: wgpu::StencilState::default(),
            bias: wgpu::DepthBiasState::default(),
        };

        let depth_state_glow = wgpu::DepthStencilState {
            format: wgpu::TextureFormat::Depth32Float,
            depth_write_enabled: false,
            depth_compare: wgpu::CompareFunction::Less,
            stencil: wgpu::StencilState::default(),
            bias: wgpu::DepthBiasState::default(),
        };

        let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("pipeline"),
            layout: Some(&pipeline_layout),
            vertex: vertex_state.clone(),
            fragment: Some(wgpu::FragmentState {
                module: &shader,
                entry_point: Some("fs_main"),
                compilation_options: Default::default(),
                targets: &[Some(wgpu::ColorTargetState {
                    format,
                    blend: Some(wgpu::BlendState::REPLACE),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
            }),
            primitive: wgpu::PrimitiveState::default(),
            depth_stencil: Some(depth_state),
            multisample: wgpu::MultisampleState::default(),
            multiview: None,
            cache: None,
        });

        let glow_pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("glow_pipeline"),
            layout: Some(&pipeline_layout),
            vertex: vertex_state,
            fragment: Some(wgpu::FragmentState {
                module: &shader,
                entry_point: Some("fs_glow"),
                compilation_options: Default::default(),
                targets: &[Some(wgpu::ColorTargetState {
                    format,
                    blend: Some(wgpu::BlendState {
                        color: wgpu::BlendComponent {
                            src_factor: wgpu::BlendFactor::One,
                            dst_factor: wgpu::BlendFactor::One,
                            operation: wgpu::BlendOperation::Add,
                        },
                        alpha: wgpu::BlendComponent {
                            src_factor: wgpu::BlendFactor::One,
                            dst_factor: wgpu::BlendFactor::One,
                            operation: wgpu::BlendOperation::Add,
                        },
                    }),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
            }),
            primitive: wgpu::PrimitiveState::default(),
            depth_stencil: Some(depth_state_glow),
            multisample: wgpu::MultisampleState::default(),
            multiview: None,
            cache: None,
        });

        Ok(Renderer {
            surface,
            device,
            queue,
            config,
            pipeline,
            glow_pipeline,
            uniform_buf,
            uniform_bgl,
            primitives,
            depth_texture: None,
            start: js_sys::Date::now(),
        })
    }

    pub fn resize(&mut self, width: u32, height: u32) {
        if width == 0 || height == 0 { return; }
        self.config.width = width;
        self.config.height = height;
        self.surface.configure(&self.device, &self.config);
        self.depth_texture = None;
    }

    pub fn render(&mut self) {
        let time = (js_sys::Date::now() - self.start) as f32 / 1000.0;

        let aspect = self.config.width as f32 / self.config.height as f32;
        let cam_angle = time * 0.3;
        let eye = [
            cam_angle.cos() * 7.0,
            3.5 + (time * 0.5).sin() * 0.5,
            cam_angle.sin() * 7.0,
        ];
        let view = look_at(eye, [0.0, 0.8, 0.0], [0.0, 1.0, 0.0]);
        let proj = perspective(45f32.to_radians(), aspect, 0.1, 100.0);
        let vp = mat4_mul(proj, view);

        let uniforms = Uniforms {
            view_proj: vp,
            camera_pos: [eye[0], eye[1], eye[2], 0.0],
            time,
            _pad1: [0f32;3],
            _pad2: [0f32;4],
        };
        self.queue.write_buffer(&self.uniform_buf, 0, bytemuck::bytes_of(&uniforms));

        let surface_tex = match self.surface.get_current_texture() {
            Ok(t) => t,
            Err(_) => return,
        };
        let view = surface_tex.texture.create_view(&wgpu::TextureViewDescriptor::default());

        if self.depth_texture.is_none() {
            self.depth_texture = Some(self.device.create_texture(&wgpu::TextureDescriptor {
                label: Some("depth"),
                size: wgpu::Extent3d {
                    width: self.config.width,
                    height: self.config.height,
                    depth_or_array_layers: 1,
                },
                mip_level_count: 1,
                sample_count: 1,
                dimension: wgpu::TextureDimension::D2,
                format: wgpu::TextureFormat::Depth32Float,
                usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
                view_formats: &[],
            }));
        }
        let depth_view = self.depth_texture.as_ref().unwrap().create_view(&wgpu::TextureViewDescriptor::default());

        let uniform_bg = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("u_bg"),
            layout: &self.uniform_bgl,
            entries: &[wgpu::BindGroupEntry {
                binding: 0,
                resource: self.uniform_buf.as_entire_binding(),
            }],
        });

        let mut encoder = self.device.create_command_encoder(&wgpu::CommandEncoderDescriptor { label: None });

        {
            let mut rpass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: None,
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &view,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color { r: 0.02, g: 0.02, b: 0.04, a: 1.0 }),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                depth_stencil_attachment: Some(wgpu::RenderPassDepthStencilAttachment {
                    view: &depth_view,
                    depth_ops: Some(wgpu::Operations {
                        load: wgpu::LoadOp::Clear(1.0),
                        store: wgpu::StoreOp::Store,
                    }),
                    stencil_ops: None,
                }),
                timestamp_writes: None,
                occlusion_query_set: None,
            });

            rpass.set_bind_group(0, &uniform_bg, &[]);
            rpass.set_pipeline(&self.pipeline);
            for p in &self.primitives {
                if !p.is_emissive {
                    rpass.set_vertex_buffer(0, p.vertex_buf.slice(..));
                    rpass.set_index_buffer(p.index_buf.slice(..), wgpu::IndexFormat::Uint16);
                    rpass.draw_indexed(0..p.index_count, 0, 0..1);
                }
            }

            rpass.set_pipeline(&self.glow_pipeline);
            for p in &self.primitives {
                if p.is_emissive {
                    rpass.set_vertex_buffer(0, p.vertex_buf.slice(..));
                    rpass.set_index_buffer(p.index_buf.slice(..), wgpu::IndexFormat::Uint16);
                    rpass.draw_indexed(0..p.index_count, 0, 0..1);
                }
            }
        }

        self.queue.submit(std::iter::once(encoder.finish()));
        surface_tex.present();
    }
}
