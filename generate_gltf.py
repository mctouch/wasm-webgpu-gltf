#!/usr/bin/env python3
"""Generate a glTF 2.0 .glb file with two boxes and a glowing cable between them."""
import struct
import json
import math

def make_box_geometry():
    """Box from -0.5 to 0.5 on each axis, 24 verts (4 per face), 36 indices."""
    # 6 faces, each with 4 vertices and proper normals
    faces = [
        # +X face
        ([0.5, -0.5, -0.5], [0.5, 0.5, -0.5], [0.5, 0.5, 0.5], [0.5, -0.5, 0.5], [1,0,0]),
        # -X face
        ([-0.5, -0.5, 0.5], [-0.5, 0.5, 0.5], [-0.5, 0.5, -0.5], [-0.5, -0.5, -0.5], [-1,0,0]),
        # +Y face
        ([-0.5, 0.5, -0.5], [-0.5, 0.5, 0.5], [0.5, 0.5, 0.5], [0.5, 0.5, -0.5], [0,1,0]),
        # -Y face
        ([-0.5, -0.5, 0.5], [-0.5, -0.5, -0.5], [0.5, -0.5, -0.5], [0.5, -0.5, 0.5], [0,-1,0]),
        # +Z face
        ([-0.5, -0.5, 0.5], [0.5, -0.5, 0.5], [0.5, 0.5, 0.5], [-0.5, 0.5, 0.5], [0,0,1]),
        # -Z face
        ([0.5, -0.5, -0.5], [-0.5, -0.5, -0.5], [-0.5, 0.5, -0.5], [0.5, 0.5, -0.5], [0,0,-1]),
    ]
    
    positions = []
    normals = []
    indices = []
    
    for i, (v0, v1, v2, v3, n) in enumerate(faces):
        base = i * 4
        for v in [v0, v1, v2, v3]:
            positions.extend(v)
            normals.extend(n)
        # Two triangles: (0,1,2) and (0,2,3)
        indices.extend([base, base+1, base+2, base, base+2, base+3])
    
    return positions, normals, indices


def make_cylinder_geometry(x1, x2, radius=0.06, segments=32):
    """Cylinder along X axis from x1 to x2."""
    N = segments
    positions = []
    normals = []
    indices = []
    
    # Bottom ring (x1)
    for i in range(N):
        theta = 2.0 * math.pi * i / N
        y = radius * math.cos(theta)
        z = radius * math.sin(theta)
        positions.extend([x1, y, z])
        normals.extend([0.0, math.cos(theta), math.sin(theta)])
    
    # Top ring (x2)
    for i in range(N):
        theta = 2.0 * math.pi * i / N
        y = radius * math.cos(theta)
        z = radius * math.sin(theta)
        positions.extend([x2, y, z])
        normals.extend([0.0, math.cos(theta), math.sin(theta)])
    
    # Bottom cap center
    positions.extend([x1, 0.0, 0.0])
    normals.extend([-1.0, 0.0, 0.0])
    # Top cap center
    positions.extend([x2, 0.0, 0.0])
    normals.extend([1.0, 0.0, 0.0])
    
    bottom_center = 2 * N
    top_center = 2 * N + 1
    
    # Side faces
    for i in range(N):
        ni = (i + 1) % N
        # bottom_i=i, bottom_next=ni, top_i=N+i, top_next=N+ni
        indices.extend([i, ni, N + ni])
        indices.extend([i, N + ni, N + i])
    
    # Bottom cap (facing -X, CCW from outside)
    for i in range(N):
        ni = (i + 1) % N
        indices.extend([bottom_center, ni, i])
    
    # Top cap (facing +X, CCW from outside)
    for i in range(N):
        ni = (i + 1) % N
        indices.extend([top_center, i, ni])
    
    return positions, normals, indices


def pack_floats(values):
    return struct.pack(f'{len(values)}f', *values)


def pack_uint16s(values):
    return struct.pack(f'{len(values)}H', *values)


def pad4(data):
    """Pad data to 4-byte alignment."""
    while len(data) % 4 != 0:
        data += b'\x00'
    return data


def main():
    # Generate geometry
    box_pos, box_nor, box_idx = make_box_geometry()
    cable_pos, cable_nor, cable_idx = make_cylinder_geometry(-1.5, 1.5, radius=0.05, segments=32)
    
    # Build binary buffer
    # Layout:
    #   box_pos:   24*3*4 = 288 bytes, offset 0
    #   box_nor:   24*3*4 = 288 bytes, offset 288
    #   box_idx:   36*2   = 72 bytes,  offset 576
    #   cable_pos: 66*3*4 = 792 bytes, offset 648
    #   cable_nor: 66*3*4 = 792 bytes, offset 1440
    #   cable_idx:  192*2  = 384 bytes, offset 2232
    # Total: 2616 bytes
    
    box_pos_bytes = pack_floats(box_pos)
    box_nor_bytes = pack_floats(box_nor)
    box_idx_bytes = pack_uint16s(box_idx)
    cable_pos_bytes = pack_floats(cable_pos)
    cable_nor_bytes = pack_floats(cable_nor)
    cable_idx_bytes = pack_uint16s(cable_idx)
    
    # Calculate offsets
    off_box_pos = 0
    off_box_nor = off_box_pos + len(box_pos_bytes)
    off_box_idx = off_box_nor + len(box_nor_bytes)
    off_cable_pos = off_box_idx + len(box_idx_bytes)
    off_cable_nor = off_cable_pos + len(cable_pos_bytes)
    off_cable_idx = off_cable_nor + len(cable_nor_bytes)
    
    bin_data = (
        box_pos_bytes + box_nor_bytes + box_idx_bytes +
        cable_pos_bytes + cable_nor_bytes + cable_idx_bytes
    )
    bin_data = pad4(bin_data)
    
    n_box_verts = len(box_pos) // 3
    n_box_idx = len(box_idx)
    n_cable_verts = len(cable_pos) // 3
    n_cable_idx = len(cable_idx)
    
    # Build glTF JSON
    gltf = {
        "asset": {"version": "2.0", "generator": "custom"},
        "scene": 0,
        "scenes": [{"nodes": [0, 1, 2]}],
        "nodes": [
            {"mesh": 0, "translation": [-2.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},  # box1
            {"mesh": 0, "translation": [2.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},   # box2
            {"mesh": 1, "translation": [0.0, 0.0, 0.0]},                              # cable
        ],
        "meshes": [
            {"primitives": [{
                "attributes": {"POSITION": 0, "NORMAL": 1},
                "indices": 2,
                "material": 0,
            }]},
            {"primitives": [{
                "attributes": {"POSITION": 3, "NORMAL": 4},
                "indices": 5,
                "material": 1,
            }]},
        ],
        "materials": [
            {
                "name": "box",
                "pbrMetallicRoughness": {
                    "baseColorFactor": [0.6, 0.65, 0.7, 1.0],
                    "metallicFactor": 0.3,
                    "roughnessFactor": 0.6,
                },
            },
            {
                "name": "cable",
                "pbrMetallicRoughness": {
                    "baseColorFactor": [0.05, 0.05, 0.08, 1.0],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.4,
                },
                "emissiveFactor": [0.2, 0.9, 0.5],
                "_emissiveIntensity": 2.0,  # custom extension for glow
            },
        ],
        "buffers": [{"byteLength": len(bin_data)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": off_box_pos, "byteLength": len(box_pos_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": off_box_nor, "byteLength": len(box_nor_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": off_box_idx, "byteLength": len(box_idx_bytes), "target": 34963},
            {"buffer": 0, "byteOffset": off_cable_pos, "byteLength": len(cable_pos_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": off_cable_nor, "byteLength": len(cable_nor_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": off_cable_idx, "byteLength": len(cable_idx_bytes), "target": 34963},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": n_box_verts, "type": "VEC3"},
            {"bufferView": 1, "componentType": 5126, "count": n_box_verts, "type": "VEC3"},
            {"bufferView": 2, "componentType": 5123, "count": n_box_idx, "type": "SCALAR"},
            {"bufferView": 3, "componentType": 5126, "count": n_cable_verts, "type": "VEC3"},
            {"bufferView": 4, "componentType": 5126, "count": n_cable_verts, "type": "VEC3"},
            {"bufferView": 5, "componentType": 5123, "count": n_cable_idx, "type": "SCALAR"},
        ],
    }
    
    # Encode GLB
    json_bytes = json.dumps(gltf, separators=(',', ':')).encode('utf-8')
    json_bytes = pad4(json_bytes)
    
    glb_header = struct.pack('<III', 0x46546C4, 2, 12 + 8 + len(json_bytes) + 8 + len(bin_data))
    json_chunk = struct.pack('<II', len(json_bytes), 0x4E4F534A) + json_bytes
    bin_chunk = struct.pack('<II', len(bin_data), 0x004E4942) + bin_data
    
    glb_data = glb_header + json_chunk + bin_chunk
    
    out_path = "www/scene.glb"
    with open(out_path, 'wb') as f:
        f.write(glb_data)
    
    print(f"Generated {out_path}: {len(glb_data)} bytes")
    print(f"  Box: {n_box_verts} verts, {n_box_idx} indices")
    print(f"  Cable: {n_cable_verts} verts, {n_cable_idx} indices")
    print(f"  Buffer: {len(bin_data)} bytes")


if __name__ == '__main__':
    main()
