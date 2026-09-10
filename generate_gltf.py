#!/usr/bin/env python3
"""Generate a glTF 2.0 .glb file with three boxes and a glowing cable that arcs above the middle box."""
import struct
import json
import math


def make_box_geometry():
    """Box from -0.5 to 0.5 on each axis, 24 verts (4 per face), 36 indices."""
    faces = [
        ([0.5, -0.5, -0.5], [0.5, 0.5, -0.5], [0.5, 0.5, 0.5], [0.5, -0.5, 0.5], [1,0,0]),
        ([-0.5, -0.5, 0.5], [-0.5, 0.5, 0.5], [-0.5, 0.5, -0.5], [-0.5, -0.5, -0.5], [-1,0,0]),
        ([-0.5, 0.5, -0.5], [-0.5, 0.5, 0.5], [0.5, 0.5, 0.5], [0.5, 0.5, -0.5], [0,1,0]),
        ([-0.5, -0.5, 0.5], [-0.5, -0.5, -0.5], [0.5, -0.5, -0.5], [0.5, -0.5, 0.5], [0,-1,0]),
        ([-0.5, -0.5, 0.5], [0.5, -0.5, 0.5], [0.5, 0.5, 0.5], [-0.5, 0.5, 0.5], [0,0,1]),
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
        indices.extend([base, base+1, base+2, base, base+2, base+3])

    return positions, normals, indices


def make_tube_along_curve(curve_fn, t_start, t_end, num_segments=64, ring_segments=24, radius=0.05):
    """Generate a tube (cylinder-like surface) along a parametric curve.

    curve_fn(t) -> (x, y, z)  for t in [t_start, t_end]

    The tube has ring_segments vertices per ring, num_segments+1 rings,
    and end caps. Normals point outward from the curve centerline.
    """
    positions = []
    normals = []
    indices = []

    # Sample the curve and compute tangents
    points = []
    tangents = []
    dt = (t_end - t_start) / num_segments

    for i in range(num_segments + 1):
        t = t_start + i * dt
        p = curve_fn(t)
        # Numerical tangent (central difference)
        eps = dt * 0.5
        if i == 0:
            p_next = curve_fn(t + eps)
            tx, ty, tz = p_next[0]-p[0], p_next[1]-p[1], p_next[2]-p[2]
        elif i == num_segments:
            p_prev = curve_fn(t - eps)
            tx, ty, tz = p[0]-p_prev[0], p[1]-p_prev[1], p[2]-p_prev[2]
        else:
            p_next = curve_fn(t + eps)
            p_prev = curve_fn(t - eps)
            tx, ty, tz = p_next[0]-p_prev[0], p_next[1]-p_prev[1], p_next[2]-p_prev[2]
        tl = math.sqrt(tx*tx + ty*ty + tz*tz)
        if tl > 1e-10:
            tx, ty, tz = tx/tl, ty/tl, tz/tl
        else:
            tx, ty, tz = 1.0, 0.0, 0.0
        points.append(p)
        tangents.append((tx, ty, tz))

    # Build rings — for each curve point, create a ring of vertices perpendicular to the tangent
    rings = []  # list of (start_index, [vertex_indices])

    for i in range(num_segments + 1):
        px, py, pz = points[i]
        tx, ty, tz = tangents[i]

        # Build a local frame: tangent = T, find two perpendicular vectors
        # Use world-up (0,1,0) to build perpendicular vectors
        # If tangent is nearly parallel to up, use (0,0,1) instead
        up = (0.0, 1.0, 0.0)
        dot = abs(tx*up[0] + ty*up[1] + tz*up[2])
        if dot > 0.99:
            up = (0.0, 0.0, 1.0)

        # u = normalize(cross(tangent, up))
        ux = ty*up[2] - tz*up[1]
        uy = tz*up[0] - tx*up[2]
        uz = tx*up[1] - ty*up[0]
        ul = math.sqrt(ux*ux + uy*uy + uz*uz)
        ux, uy, uz = ux/ul, uy/ul, uz/ul

        # v = cross(tangent, u) — already unit length
        vx = ty*uz - tz*uy
        vy = tz*ux - tx*uz
        vz = tx*uy - ty*ux

        ring_start = len(positions) // 3

        for j in range(ring_segments):
            theta = 2.0 * math.pi * j / ring_segments
            cos_t = math.cos(theta)
            sin_t = math.sin(theta)

            # Vertex position = center + radius * (cos*U + sin*V)
            vx_pos = px + radius * (cos_t * ux + sin_t * vx)
            vy_pos = py + radius * (cos_t * uy + sin_t * vy)
            vz_pos = pz + radius * (cos_t * uz + sin_t * vz)

            positions.extend([vx_pos, vy_pos, vz_pos])
            # Normal = outward direction (cos*U + sin*V), normalized
            normals.extend([
                cos_t * ux + sin_t * vx,
                cos_t * uy + sin_t * vy,
                cos_t * uz + sin_t * vz,
            ])

        rings.append(ring_start)

    # Side faces — connect ring i to ring i+1
    for i in range(num_segments):
        r0 = rings[i]
        r1 = rings[i + 1]
        for j in range(ring_segments):
            nj = (j + 1) % ring_segments
            # Triangle 1: r0+j, r0+nj, r1+nj
            indices.extend([r0 + j, r0 + nj, r1 + nj])
            # Triangle 2: r0+j, r1+nj, r1+j
            indices.extend([r0 + j, r1 + nj, r1 + j])

    # End caps
    # Start cap center
    start_center_idx = len(positions) // 3
    positions.extend([points[0][0], points[0][1], points[0][2]])
    # Normal points backward (opposite to tangent at start)
    normals.extend([-tangents[0][0], -tangents[0][1], -tangents[0][2]])

    # End cap center
    end_center_idx = len(positions) // 3
    positions.extend([points[-1][0], points[-1][1], points[-1][2]])
    normals.extend([tangents[-1][0], tangents[-1][1], tangents[-1][2]])

    # Start cap triangles (facing backward, CCW from outside)
    r0 = rings[0]
    for j in range(ring_segments):
        nj = (j + 1) % ring_segments
        indices.extend([start_center_idx, r0 + nj, r0 + j])

    # End cap triangles (facing forward, CCW from outside)
    r_last = rings[-1]
    for j in range(ring_segments):
        nj = (j + 1) % ring_segments
        indices.extend([end_center_idx, r_last + j, r_last + nj])

    return positions, normals, indices


def pack_floats(values):
    return struct.pack(f'{len(values)}f', *values)


def pack_uint16s(values):
    return struct.pack(f'{len(values)}H', *values)


def pad4(data):
    while len(data) % 4 != 0:
        data += b'\x00'
    return data


def main():
    # Generate box geometry (reused for all three boxes)
    box_pos, box_nor, box_idx = make_box_geometry()

    # Cable path: rectangular stepped route with curved corners that clears the middle box
    # Left box top is at y=0.5 (box at x=-2, half-size 0.5)
    # Middle box top is at y=0.5 (box at x=0)
    # Right box top is at y=0.5 (box at x=2)
    #
    # The cable goes: up from left box top -> curve right -> across above middle box ->
    #   curve down -> down to right box top
    #
    # Corner radius for the rounded turns
    R = 0.4
    y_low = 0.5    # box top height
    y_high = 1.5   # horizontal run height
    x_left = -2.0
    x_right = 2.0

    # The path has 5 segments:
    #   1. Straight up:    (-2.0, 0.5) -> (-2.0, 1.5-R)
    #   2. Quarter circle:  (-2.0, 1.5-R) -> (-2.0+R, 1.5)  [center at (-2.0+R, 1.5-R)]
    #   3. Straight across: (-2.0+R, 1.5) -> (2.0-R, 1.5)
    #   4. Quarter circle:  (2.0-R, 1.5) -> (2.0, 1.5-R)    [center at (2.0-R, 1.5-R)]
    #   5. Straight down:  (2.0, 1.5-R) -> (2.0, 0.5)

    def stepped_curve(t):
        # t in [0, 1] over the whole path
        # Compute segment lengths
        seg_lens = [
            y_high - R - y_low,                     # 1. straight up
            0.5 * math.pi * R,                       # 2. quarter circle
            (x_right - R) - (x_left + R),            # 3. straight across
            0.5 * math.pi * R,                       # 4. quarter circle
            y_high - R - y_low,                      # 5. straight down
        ]
        total = sum(seg_lens)
        target = t * total
        acc = 0.0
        for i, sl in enumerate(seg_lens):
            if acc + sl >= target or i == len(seg_lens) - 1:
                local = (target - acc) / sl if sl > 1e-10 else 0.0
                if i == 0:
                    return (x_left, y_low + local * sl, 0.0)
                elif i == 1:
                    # Quarter circle: center at (x_left+R, y_high-R), from angle pi to pi/2
                    angle = math.pi - local * 0.5 * math.pi
                    return (x_left + R + R * math.cos(angle), y_high - R + R * math.sin(angle), 0.0)
                elif i == 2:
                    return (x_left + R + local * sl, y_high, 0.0)
                elif i == 3:
                    # Quarter circle: center at (x_right-R, y_high-R), from angle pi/2 to 0
                    angle = 0.5 * math.pi - local * 0.5 * math.pi
                    return (x_right - R + R * math.cos(angle), y_high - R + R * math.sin(angle), 0.0)
                elif i == 4:
                    return (x_right, y_high - R - local * sl, 0.0)
            acc += sl
        return (x_right, y_low, 0.0)


    cable_pos, cable_nor, cable_idx = make_tube_along_curve(
        stepped_curve, t_start=0.0, t_end=1.0,
        num_segments=64, ring_segments=20, radius=0.045,
    )

    # Build binary buffer
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
        "scenes": [{"nodes": [0, 1, 2, 3]}],
        "nodes": [
            {"mesh": 0, "translation": [-2.0, 0.0, 0.0]},   # left box
            {"mesh": 0, "translation": [0.0, 0.0, 0.0]},     # middle box
            {"mesh": 0, "translation": [2.0, 0.0, 0.0]},     # right box
            {"mesh": 1},                                       # cable (world-space, no transform)
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
    print(f"  Box:    {n_box_verts} verts, {n_box_idx} indices (x3 boxes)")
    print(f"  Cable:  {n_cable_verts} verts, {n_cable_idx} indices (curved tube)")
    print(f"  Buffer: {len(bin_data)} bytes")


if __name__ == '__main__':
    main()
