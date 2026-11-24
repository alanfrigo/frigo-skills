#!/usr/bin/env python3
"""Preflight and run local ComfyUI mesh workflows over its native HTTP API."""

import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import struct
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import uuid4

WORKFLOWS = Path(__file__).resolve().parent.parent / "workflows"
PIPELINES = ("trellis2", "pixal3d", "hunyuan-mv")
VIEWS = ("front", "left", "back", "right")
SAVE_CLASSES = {"SaveGLB", "Save3DAdvanced"}
TRELLIS_OPTIONS = ("resolution", "map_size", "normal_size", "ao_size", "mask", "fov", "solid_remesh")
MODEL_FIELDS = {
    "UNETLoader": "unet_name", "VAELoader": "vae_name", "CLIPVisionLoader": "clip_name",
    "LoadBackgroundRemovalModel": "bg_removal_name", "LoadMoGeModel": "model_name",
    "ImageOnlyCheckpointLoader": "ckpt_name",
}
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
MIB = 1024 * 1024


class Problem(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def loopback(value):
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or not parsed.hostname or parsed.path not in ("", "/")
            or parsed.username is not None or parsed.query or parsed.fragment):
        raise Problem("--server must be a plain loopback HTTP URL, e.g. http://127.0.0.1:8188")
    host = parsed.hostname
    if host == "localhost":
        host = "127.0.0.1"
    try:
        address, port = ipaddress.ip_address(host), parsed.port
    except ValueError as exc:
        raise Problem(f"Invalid loopback address or port in {value!r}") from exc
    if not address.is_loopback or "%" in host:
        raise Problem("Only loopback ComfyUI servers are allowed; run the client on the server machine")
    host = f"[{address}]" if address.version == 6 else str(address)
    return f"http://{host}" + (f":{port}" if port is not None else "")


class Client:
    def __init__(self, server, seconds):
        self.server = loopback(server)
        self.deadline = time.monotonic() + seconds
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def remaining(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise Problem("Timeout waiting for local ComfyUI; check its queue and server log")
        return remaining

    def chunks(self, response):
        while True:
            self.remaining()
            chunk = response.read1(1024 * 1024)
            if not chunk:
                return
            yield chunk

    def open(self, route, body=None, content_type="application/json"):
        headers = {"Content-Type": content_type} if body is not None else {}
        request = Request(self.server + route, data=body, headers=headers)
        try:
            return self.opener.open(request, timeout=min(30, self.remaining()))
        except HTTPError as exc:
            with exc:
                detail = exc.read1(16 * 1024).decode("utf-8", errors="replace").strip()
            raise Problem(f"{route} returned HTTP {exc.code}: {detail or exc.reason}") from exc
        except (URLError, TimeoutError) as exc:
            raise Problem(f"Cannot reach {self.server}{route}: {exc}. Check the port and ComfyUI server log.") from exc

    def json(self, route, body=None, content_type="application/json"):
        data = bytearray()
        with self.open(route, body, content_type) as response:
            for chunk in self.chunks(response):
                data.extend(chunk)
                if len(data) > 64 * MIB:
                    raise Problem(f"Oversized JSON response from {route}")
        try:
            value = json.loads(data)
        except ValueError as exc:
            raise Problem(f"Expected JSON from {route}; is this a compatible local ComfyUI server?") from exc
        if not isinstance(value, dict):
            raise Problem(f"Expected a JSON object from {route}")
        return value

    def stats(self):
        response = self.json("/system_stats")
        system = response.get("system", {})
        return {
            "comfyui_version": system.get("comfyui_version"),
            "pytorch_version": system.get("pytorch_version"),
            "os": system.get("os"),
            "devices": [{key: item.get(key) for key in ("name", "type", "index", "vram_total", "vram_free")}
                        for item in response.get("devices", [])],
        }

    def upload(self, path, folder, index):
        suffix = path.suffix.lower()
        with path.open("rb") as stream:
            data = stream.read(32 * MIB + 1)
        if not 0 < len(data) <= 32 * MIB:
            raise Problem(f"{path}: image must be nonempty and no larger than 32 MiB")
        filename = f"image-{index}{suffix}"
        boundary = uuid4().hex
        parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'
                 for key, value in (("type", "input"), ("subfolder", folder), ("overwrite", "false"))]
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{filename}"\r\n'
                     f"Content-Type: {IMAGE_TYPES[suffix]}\r\n\r\n")
        body = "".join(parts).encode() + data + f"\r\n--{boundary}--\r\n".encode()
        uploaded = self.json("/upload/image", body, f"multipart/form-data; boundary={boundary}")
        if (uploaded.get("type"), uploaded.get("subfolder"), uploaded.get("name")) != ("input", folder, filename):
            raise Problem(f"Unexpected upload location for {path}: {uploaded}")
        return {"local_path": str(path.resolve()), "server_image": f"{folder}/{filename}",
                "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def node(class_type, **inputs):
    return {"class_type": class_type, "inputs": inputs}


def read_graph(path):
    graph = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(graph, dict) or not graph or any(
        not isinstance(item, dict) or not isinstance(item.get("class_type"), str)
        or not isinstance(item.get("inputs"), dict) for item in graph.values()
    ):
        raise Problem(f"{path}: use a node-ID-keyed Save (API Format) graph, not UI/template JSON or a /prompt envelope")
    return graph


def assign(text):
    key, sep, value = text.partition("=")
    if not sep or not key or not value:
        raise Problem(f"Expected KEY=VALUE, got {text!r}")
    return key, value


def link(value):
    return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and type(value[1]) is int


def ancestors(graph, save):
    reachable, visiting = set(), set()

    def visit(current):
        if current in visiting:
            raise Problem(f"Workflow dependency cycle at node {current}")
        if current in reachable:
            return
        if current not in graph:
            raise Problem(f"Workflow links to missing node {current}")
        visiting.add(current)
        for item in graph[current]["inputs"].values():
            if link(item):
                visit(item[0])
        visiting.remove(current)
        reachable.add(current)

    visit(save)
    return {key: item for key, item in graph.items() if key in reachable}


def source_image(uploads, current, path):
    if current in uploads:
        raise Problem(f"Image supplied twice for node {current}")
    if path.suffix.lower() not in IMAGE_TYPES or not path.is_file():
        raise Problem(f"{path}: supply an existing PNG, JPEG or WebP file")
    if not 0 < path.stat().st_size <= 32 * MIB:
        raise Problem(f"{path}: image must be nonempty and no larger than 32 MiB")
    uploads[current] = path


def require_alpha(path):
    with path.open("rb") as stream:
        header = stream.read(29)
    if len(header) >= 26 and header.startswith(b"\x89PNG\r\n\x1a\n") and header[12:16] == b"IHDR":
        if header[25] in (4, 6):  # grayscale + alpha or RGBA
            return
    if len(header) >= 25 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        if header[12:16] == b"VP8X" and header[20] & 0x10:
            return
        if header[12:16] == b"VP8L" and header[20] == 0x2F:
            if int.from_bytes(header[21:25], "little") & (1 << 28):
                return
    raise Problem(f"{path}: --mask alpha requires an alpha-bearing PNG or WebP; use --mask birefnet otherwise")


def configure(args):
    uploads, expected = {}, set()
    view_paths = {view: getattr(args, view) for view in VIEWS}
    has_trellis_opts = any(getattr(args, option) is not None for option in TRELLIS_OPTIONS)
    if args.workflow:
        if (args.profile or args.image or any(view_paths.values()) or has_trellis_opts or args.geometry_only
                or any(getattr(args, key) is not None for key in ("steps", "triangles", "octree_resolution"))):
            raise Problem("With --workflow use --set, --image-node, --seed and --save-node; profile controls are for bundled workflows")
        graph = read_graph(args.workflow)
        overridden = set()
        for override in args.set:
            key, value = assign(override)
            current, sep, field = key.partition(".")
            if not sep or not field or current not in graph or field == "filename_prefix":
                raise Problem(f"Invalid --set target {key!r}; use NODE.FIELD other than filename_prefix")
            graph[current]["inputs"][field] = json.loads(value)
            overridden.add(current)
        for image in args.image_node:
            current, file = assign(image)
            if graph.get(current, {}).get("class_type") != "LoadImage":
                raise Problem(f"--image-node {current}: target must be a LoadImage node")
            source_image(uploads, current, Path(file))
        saves = [key for key, item in graph.items() if item["class_type"] in SAVE_CLASSES]
        save = args.save_node or (saves[0] if len(saves) == 1 else None)
        if save not in saves:
            raise Problem("Supply a native SaveGLB or Save3DAdvanced output; choose one with --save-node NODE if needed")
        graph = ancestors(graph, save)
        if unused := (overridden | uploads.keys()) - graph.keys():
            raise Problem(f"Override nodes are outside the selected output: {', '.join(sorted(unused))}")
        settings = {"pipeline": "api", "source_workflow": str(args.workflow.resolve())}
        required_uploads = set(uploads)
        if args.seed is not None:
            changed = 0
            for item in graph.values():
                for field in ("seed", "noise_seed"):
                    if type(item["inputs"].get(field)) is int:
                        item["inputs"][field] = args.seed
                        changed += 1
            if not changed:
                raise Problem("No literal seed or noise_seed input to replace; use --set on the upstream seed node")
    else:
        if args.set or args.image_node or args.save_node:
            raise Problem("--set, --image-node and --save-node require --workflow")
        graph = read_graph(WORKFLOWS / f"{args.pipeline}-api.json")
        quick = args.profile != "detail"
        settings = {"pipeline": args.pipeline, "profile": "quick" if quick else "detail"}
        seed = 42 if args.seed is None else args.seed
        required_uploads = {"1"}
        if args.pipeline == "hunyuan-mv":
            if args.image or has_trellis_opts or args.geometry_only:
                raise Problem("hunyuan-mv is geometry-only; use --front and optional --left, --back, --right")
            for i, (view, path) in enumerate(view_paths.items()):
                if path is None:
                    continue
                current = "1" if view == "front" else str(20 + i * 2)
                source_image(uploads, current, path)
                if view != "front":
                    encoder = str(int(current) + 1)
                    graph[current] = node("LoadImage", image=f"{view}.png")
                    graph[encoder] = node("CLIPVisionEncode", clip_vision=["2", 1], image=[current, 0], crop="none")
                    graph["4"]["inputs"][view] = [encoder, 0]
            octree = args.octree_resolution or (128 if quick else 256)
            steps = args.steps or (12 if quick else 20)
            graph["7"]["inputs"].update(seed=seed, steps=steps)
            graph["8"]["inputs"]["octree_resolution"] = octree
            if args.triangles:
                graph["11"] = node("DecimateMesh", mesh=["9", 0], target_face_count=args.triangles,
                                   placement_mode="midpoint")
                graph["10"]["inputs"]["mesh"] = ["11", 0]
            save = "10"
            settings.update(steps={"shape": steps}, octree_resolution=octree, triangles=args.triangles,
                            material="geometry", views=list(graph["4"]["inputs"]))
        else:
            if any(view_paths.values()) or args.octree_resolution:
                raise Problem("--front/--left/--back/--right and --octree-resolution require hunyuan-mv")
            if args.image is not None:
                source_image(uploads, "1", args.image)
            if args.fov is not None and args.pipeline != "pixal3d":
                raise Problem("--fov requires pixal3d")
            if args.geometry_only and any(value is not None for value in (args.map_size, args.normal_size, args.ao_size)):
                raise Problem("Map size controls require a textured run (omit --geometry-only)")
            resolution = args.resolution or (512 if quick else 1024)
            triangles = args.triangles if args.triangles is not None else (35000 if quick else 150000)
            mask = args.mask or "birefnet"
            if mask == "alpha":
                if args.image is not None:
                    require_alpha(args.image)
                graph["31"] = node("InvertMask", mask=["1", 1])
                graph["4"]["inputs"]["masks"] = ["31", 0]
            if args.pipeline == "pixal3d":
                fov = args.fov if args.fov is not None else 49.13
                if fov == "auto":
                    graph["32"] = node("LoadMoGeModel", model_name="moge_2_vitl_normal_fp16.safetensors")
                    graph["33"] = node("MoGeInference", moge_model=["32", 0], image=["4", 0],
                                       resolution_level=5 if quick else 9, fov_x_degrees=0.0, batch_size=1,
                                       force_projection=True, apply_mask=True, refine_steps=3)
                    graph["34"] = node("MoGeGeometryToFOV", moge_geometry=["33", 0], axis="horizontal", unit="degrees")
                    graph["6"]["inputs"]["camera_angle_x"] = ["34", 0]
                else:
                    graph["6"]["inputs"]["camera_angle_x"] = fov
                settings["horizontal_fov"] = fov
            settings.update(resolution=resolution, triangles=triangles, mask=mask, steps={},
                            solid_remesh=args.solid_remesh)
            samplers = [("structure", "12", 6 if quick else 12), ("shape", "18", 6 if quick else 20)]
            if resolution > 512:
                graph["35"] = node("Trellis2UpsampleStage", positive=["15", 0], negative=["15", 1],
                                   shape_latent=["18", 0], vae=["13", 0], target_resolution=resolution)
                graph["36"] = node("KSampler", **graph["18"]["inputs"])
                graph["36"]["inputs"].update(positive=["35", 0], negative=["35", 1], latent_image=["35", 2], scheduler="simple")
                graph["19"]["inputs"]["samples"] = ["36", 0]
                graph["20"]["inputs"].update(positive=["35", 0], negative=["35", 1], shape_latent=["36", 0])
                samplers.append(("refine", "36", 6 if quick else 12))
            graph["24"]["inputs"]["target_face_count"] = triangles
            if args.solid_remesh is not None:
                graph["39"] = node("RemeshMesh", mesh=["19", 0], resolution=args.solid_remesh,
                                   sign_mode="solid", band=1.0, project_back=0.0, fix_poles=False,
                                   smooth_iters=20, drop_small_components=0.01, precluster_max_verts=20000000,
                                   **{"sign_mode.fill": 20.0, "sign_mode.qef": False})
                graph["24"]["inputs"]["mesh"] = ["39", 0]
            save = "30"
            if args.geometry_only:
                graph[save]["inputs"]["mesh"] = ["25", 0]
                settings["material"] = "geometry"
            else:
                map_size = args.map_size or (512 if quick else 1024)
                graph["26"]["inputs"]["resolution"] = map_size
                graph["27"]["inputs"]["texture_size"] = map_size
                samplers.append(("texture", "21", 6 if quick else 12))
                expected = {"baseColorTexture", "metallicRoughnessTexture"}
                if args.normal_size:
                    graph["37"] = node("BakeNormalMapFromMesh", low_poly=["26", 0], high_poly=["19", 0],
                                       resolution=args.normal_size, cage_distance=0.05, ignore_backfaces=True)
                    graph["28"]["inputs"]["normal_map"] = ["37", 0]
                    expected.add("normalTexture")
                if args.ao_size:
                    # Native GLB packs AO into the red channel of the metallic/roughness atlas.
                    if args.ao_size != map_size:
                        raise Problem("--ao-size must equal --map-size (or the profile's atlas size) for ORM packing")
                    graph["38"] = node("BakeAmbientOcclusion", low_poly=["26", 0], high_poly=["19", 0],
                                       resolution=args.ao_size, samples=32, max_distance=0.71, strength=1.0, bias=0.01)
                    graph["28"]["inputs"]["occlusion"] = ["38", 0]
                    expected.add("occlusionTexture")
                settings.update(material="pbr", map_size=map_size, normal_size=args.normal_size, ao_size=args.ao_size)
            for label, current, default_steps in samplers:
                steps = args.steps or default_steps
                graph[current]["inputs"].update(seed=seed, steps=steps)
                settings["steps"][label] = steps
        graph = ancestors(graph, save)
        if args.command == "run" and not required_uploads <= uploads.keys():
            raise Problem("A source image is required: use --front for hunyuan-mv, otherwise --image")
    settings["seeds"] = {key: {field: value for field, value in item["inputs"].items()
                                if field in {"seed", "noise_seed"}}
                         for key, item in graph.items() if {"seed", "noise_seed"} & item["inputs"].keys()}
    return graph, save, uploads, required_uploads, settings, expected


def native_preflight(graph, info, skip_uploads):
    errors, models = [], []
    for key, item in graph.items():
        class_type, inputs = item["class_type"], item["inputs"]
        label = f"node {key} ({class_type})"
        spec = info.get(class_type)
        if spec is None:
            errors.append(f"{label}: missing from /object_info. Update ComfyUI or check startup imports.")
            continue
        module = spec.get("python_module", "")
        if spec.get("api_node") or not (module == "nodes" or module.startswith("comfy_extras.")):
            errors.append(f"{label}: not a permitted native local node ({module or 'unknown module'})")
            continue
        schema = spec.get("input", {})
        required, optional = schema.get("required", {}), schema.get("optional", {})
        for field in required.keys() - inputs.keys():
            errors.append(f"{label}: missing required input {field}")
        fields = required | optional
        for field, value in inputs.items():
            base = field.split(".", 1)[0]
            definition = fields.get(field)
            if definition is None:
                if base not in fields or not str(fields[base][0]).startswith("COMFY_DYNAMIC"):
                    errors.append(f"{label}: unknown input {field}")
                continue
            kind = definition[0]
            meta = definition[1] if len(definition) > 1 else {}
            if link(value):
                target = info.get(graph[value[0]]["class_type"], {})
                if target and not 0 <= value[1] < len(target.get("output", [])):
                    errors.append(f"{label}.{field}: invalid output slot {value[0]}:{value[1]}")
                continue
            if key in skip_uploads and class_type == "LoadImage" and field == "image":
                continue
            options = kind if isinstance(kind, list) else meta.get("options") if kind == "COMBO" else None
            if options is not None and value not in options:
                errors.append(f"{label}.{field}: {value!r} not listed by server; install the file or select an available value")
            if field == MODEL_FIELDS.get(class_type):
                models.append({"node": key, "class_type": class_type, "filename": value})
    if errors:
        raise Problem("Preflight failed:\n  " + "\n  ".join(errors))
    return models


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def seconds_since(start):
    return round(time.monotonic() - start, 3)


def poll(client, prompt_id, interval):
    route = "/history/" + quote(prompt_id, safe="")
    while True:
        record = client.json(route).get(prompt_id)
        if isinstance(record, dict) and record.get("status"):
            return record
        time.sleep(min(interval, client.remaining()))


def history_timing(record):
    prompt = record.get("prompt")
    queued = prompt[3].get("create_time") if isinstance(prompt, list) and len(prompt) > 3 and isinstance(prompt[3], dict) else None
    events = {name: item.get("timestamp") for name, item in record["status"].get("messages", [])}
    start = events.get("execution_start")
    end = next((events[name] for name in ("execution_success", "execution_error", "execution_interrupted") if name in events), None)
    result = {"queued_ms": queued, "started_ms": start, "finished_ms": end}
    for key, begin, finish in (("queue_s", queued, start), ("execution_s", start, end)):
        if isinstance(begin, (int, float)) and isinstance(finish, (int, float)) and finish >= begin:
            result[key] = round((finish - begin) / 1000, 3)
    return result


def check_status(status):
    if status.get("status_str") == "success" and status.get("completed") is True:
        return
    for event, data in reversed(status.get("messages", [])):
        if event not in {"execution_error", "execution_interrupted"}:
            continue
        message = data.get("exception_message") or event
        hint = "See the local ComfyUI log for details."
        if "out of memory" in message.lower() or "outofmemory" in str(data.get("exception_type", "")).lower():
            hint = "Retry the quick profile at 512; reduce atlas/face target or use --geometry-only. Check free VRAM on the active GPU."
        raise Problem(f"ComfyUI node {data.get('node_id')} ({data.get('node_type')}): {message}. {hint}")
    raise Problem(f"ComfyUI did not report successful completion: {status.get('status_str', 'missing status')}")


def output_files(record, save, folder):
    files = record.get("outputs", {}).get(save, {}).get("3d", [])
    matches = []
    for item in files:
        filename = item.get("filename", "")
        if (item.get("type") == "output" and item.get("subfolder", "").replace("\\", "/") == folder
                and re.fullmatch(r"mesh_[0-9]+_?\.glb", filename, flags=re.IGNORECASE)):
            matches.append({"filename": filename, "subfolder": item["subfolder"], "type": "output"})
    if not matches:
        raise Problem(f"Save node {save} yielded no GLB with prefix {folder}/mesh in this prompt's history. Check the save format and mesh output.")
    return matches


def verify_glb(path, size, expected):
    with path.open("rb") as stream:
        header = stream.read(20)
        if len(header) != 20:
            raise Problem("Downloaded GLB header is truncated")
        magic, version, declared, json_size, json_kind = struct.unpack("<4sIII4s", header)
        if (magic, version, declared, json_kind) != (b"glTF", 2, size, b"JSON") or not 0 < json_size <= min(size - 20, 64 * MIB):
            raise Problem("Downloaded file is not a complete GLB 2.0 container")
        try:
            gltf = json.loads(stream.read(json_size))
            bin_header = stream.read(8)
            if len(bin_header) != 8:
                raise Problem("Downloaded GLB has no embedded mesh buffer")
            bin_size, bin_kind = struct.unpack("<I4s", bin_header)
            if bin_kind != b"BIN\0" or not 0 < bin_size <= size - 28 - json_size:
                raise Problem("Downloaded GLB has a missing or truncated BIN chunk")
            if gltf["asset"]["version"] != "2.0":
                raise Problem("Downloaded glTF JSON does not declare version 2.0")
            accessors, materials = gltf.get("accessors", []), gltf.get("materials", [])
            triangles, maps = 0, set()
            for mesh in gltf.get("meshes", []):
                for primitive in mesh.get("primitives", []):
                    mode = primitive.get("mode", 4)
                    position = primitive.get("attributes", {}).get("POSITION")
                    if mode not in (4, 5, 6) or position is None or accessors[position]["count"] < 3:
                        continue
                    count = accessors[primitive.get("indices", position)]["count"]
                    triangles += count // 3 if mode == 4 else max(0, count - 2)
                    if "material" in primitive:
                        mat = materials[primitive["material"]]
                        pbr = mat.get("pbrMetallicRoughness", {})
                        for field in expected:
                            texture = mat.get(field) or pbr.get(field)
                            if texture is None:
                                continue
                            tex = gltf["textures"][texture["index"]]
                            image = gltf["images"][tex["source"]]
                            view = gltf["bufferViews"][image["bufferView"]]
                            offset, length = view.get("byteOffset", 0), view["byteLength"]
                            if view["buffer"] == 0 and offset >= 0 and 0 < length <= bin_size - offset:
                                maps.add(field)
        except (ValueError, TypeError, AttributeError, IndexError, KeyError) as exc:
            raise Problem(f"Invalid glTF JSON in downloaded GLB: {exc}") from exc
    if triangles <= 0:
        raise Problem("Downloaded GLB contains no nonempty triangle mesh")
    if expected - maps:
        raise Problem(f"Downloaded GLB is missing expected maps: {', '.join(sorted(expected - maps))}")
    return {"triangles": triangles, "verified_maps": sorted(maps)}


def download(client, descriptor, run_dir, expected):
    target = run_dir / descriptor["filename"]
    temporary = target.with_suffix(".part")
    digest, size = hashlib.sha256(), 0
    try:
        route = "/view?" + urlencode(descriptor)
        with client.open(route) as response, temporary.open("xb") as stream:
            for chunk in client.chunks(response):
                digest.update(chunk)
                size += len(chunk)
                stream.write(chunk)
        observed = verify_glb(temporary, size, expected)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return {"path": str(target), "bytes": size, "sha256": digest.hexdigest(), "server_file": descriptor, **observed}


def execute(args):
    start = time.monotonic()
    graph, save, uploads, required_uploads, settings, expected = configure(args)
    client = Client(args.server, args.timeout)
    upload_nodes = required_uploads | uploads.keys()
    models = native_preflight(graph, client.json("/object_info"), upload_nodes)
    report = {"server": client.server, "server_info": client.stats(), "settings": settings, "models": models,
              "save_node": save}
    if args.command == "inspect":
        return {**report, "status": "ready", "nodes": {key: item["class_type"] for key, item in graph.items()},
                "upload_nodes": sorted(upload_nodes)}

    run_id = f"{args.name}-{uuid4().hex}"
    folder = f"asset-3d/{run_id}"
    run_dir = args.out_dir.resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = run_dir / "manifest.json"
    workflow_path = run_dir / "workflow-api.json"
    timings = {"preflight_s": seconds_since(start)}
    report.update(status="preparing", run_id=run_id, run_dir=str(run_dir), manifest=str(manifest_path),
                  workflow=str(workflow_path), output_prefix=f"{folder}/mesh", inputs={}, artifacts=[],
                  timings=timings, started_at=utc_now())
    try:
        write_json(manifest_path, report)
        phase = time.monotonic()
        for i, (key, path) in enumerate(uploads.items(), 1):
            image = client.upload(path, folder, i)
            report["inputs"][key] = image
            graph[key]["inputs"]["image"] = image["server_image"]
        timings["upload_s"] = seconds_since(phase)
        graph[save]["inputs"]["filename_prefix"] = report["output_prefix"]
        write_json(workflow_path, graph)
        phase = time.monotonic()
        report["submitted_at"] = utc_now()
        queued = client.json("/prompt", json.dumps({"prompt": graph}, allow_nan=False).encode())
        prompt_id = queued.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise Problem(f"ComfyUI did not accept the graph: {queued}")
        timings["submit_s"] = seconds_since(phase)
        report.update(prompt_id=prompt_id, queue_number=queued.get("number"), status="queued")
        write_json(manifest_path, report)
        print(f"Queued {prompt_id} at {client.server}; manifest: {manifest_path}", file=sys.stderr, flush=True)
        if queued.get("node_errors"):
            raise Problem(f"ComfyUI reported validation errors when queuing: {queued['node_errors']}")
        phase = time.monotonic()
        record = poll(client, prompt_id, args.poll_interval)
        timings["poll_s"] = seconds_since(phase)
        timings["server"] = history_timing(record)
        report["history_path"] = str(run_dir / "history.json")
        write_json(run_dir / "history.json", record)
        check_status(record["status"])
        phase = time.monotonic()
        for descriptor in output_files(record, save, folder):
            report["artifacts"].append(download(client, descriptor, run_dir, expected))
        timings["download_and_verify_s"] = seconds_since(phase)
        report.update(status="success", artifact=report["artifacts"][0]["path"])
    except (Problem, OSError, ValueError, KeyboardInterrupt) as exc:
        report.update(status="interrupted" if isinstance(exc, KeyboardInterrupt) else "failed",
                      error=str(exc) or "Interrupted by caller")
        if report.get("prompt_id"):
            print(f"Prompt {report['prompt_id']} was not cancelled; check its exact history or the local ComfyUI queue.",
                  file=sys.stderr)
        print(f"Run record: {manifest_path}", file=sys.stderr)
        raise
    finally:
        timings["total_s"] = seconds_since(start)
        report["finished_at"] = utc_now()
        write_json(manifest_path, report)
    return report


def bounded(low, high, step=1):
    def parse(value):
        try:
            result = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("expected an integer") from exc
        if not low <= result <= high or result % step:
            raise argparse.ArgumentTypeError(f"expected {low}–{high}" + (f", multiple of {step}" if step > 1 else ""))
        return result
    return parse


def period(value):
    seconds = float(value)
    if not 0.1 <= seconds <= 86400:
        raise argparse.ArgumentTypeError("expected seconds between 0.1 and 86400")
    return seconds


def fov(value):
    if value == "auto":
        return value
    numeric = float(value)
    if not 1 <= numeric <= 170:
        raise argparse.ArgumentTypeError("expected horizontal degrees between 1 and 170, or auto")
    return numeric


def name(value):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,39}", value):
        raise argparse.ArgumentTypeError("expected 1–40 letters, digits, hyphens or underscores, starting alphanumeric")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_subparsers(dest="command", required=True)
    for command in ("inspect", "run"):
        sub = mode.add_parser(command, help="Read-only schema/model preflight" if command == "inspect" else "Queue and retrieve verified GLB")
        selected = sub.add_mutually_exclusive_group(required=True)
        selected.add_argument("--pipeline", choices=PIPELINES, help="Bundled native API workflow")
        selected.add_argument("--workflow", type=Path, help="User-supplied native ComfyUI API graph")
        sub.add_argument("--server", default="http://127.0.0.1:8188", help="Loopback base URL (default: %(default)s)")
        sub.add_argument("--timeout", type=period, default=900, metavar="SECONDS", help="Total network wait budget (default: %(default)s)")
        sub.add_argument("--profile", choices=("quick", "detail"), help="Bundled profiles (default: quick)")
        sub.add_argument("--image", type=Path, help="Source PNG/JPEG/WebP for TRELLIS.2 or Pixal3D")
        for view in VIEWS:
            sub.add_argument(f"--{view}", type=Path, help=f"Hunyuan multiview {view} image")
        sub.add_argument("--seed", type=bounded(0, 2**64 - 1), help="Replace literal seeds (bundled default: 42)")
        sub.add_argument("--steps", type=bounded(1, 10000), help="Sampling steps per active stage")
        sub.add_argument("--resolution", type=int, choices=(512, 1024, 1536), help="TRELLIS/Pixal shape resolution")
        sub.add_argument("--triangles", type=bounded(0, 50000000), help="Mesh decimation target; 0 disables")
        sub.add_argument("--solid-remesh", type=bounded(32, 512), metavar="N", help="TRELLIS/Pixal: opt into solid voxel remesh at resolution N (32-512)")
        sub.add_argument("--map-size", type=bounded(256, 8192, 256), help="PBR atlas size in pixels")
        sub.add_argument("--normal-size", type=bounded(64, 8192, 64), help="Opt into a tangent-space normal bake at this size")
        sub.add_argument("--ao-size", type=bounded(256, 8192, 256), help="Opt into ambient occlusion at the atlas size")
        sub.add_argument("--mask", choices=("birefnet", "alpha"), help="Foreground mask source (default: birefnet)")
        sub.add_argument("--fov", type=fov, help="Pixal3D horizontal FOV in degrees (default: 49.13) or auto (MoGe)")
        sub.add_argument("--octree-resolution", type=bounded(16, 512), help="Hunyuan mesh extraction resolution")
        sub.add_argument("--geometry-only", action="store_true", help="Skip texture generation, UVs and baking")
        sub.add_argument("--set", action="append", default=[], metavar="NODE.FIELD=JSON", help="Override an API graph input")
        sub.add_argument("--image-node", action="append", default=[], metavar="NODE=PATH", help="Upload an image for a LoadImage node")
        sub.add_argument("--save-node", help="Select one save node from a user-supplied API graph")
        if command == "run":
            sub.add_argument("--out-dir", type=Path, required=True, help="Parent directory for the new run directory")
            sub.add_argument("--name", type=name, default="mesh", help="Prefix of the unique run directory name")
            sub.add_argument("--poll-interval", type=period, default=1.0, metavar="SECONDS", help="History polling interval (default: %(default)s)")
    args = parser.parse_args()
    try:
        print(json.dumps(execute(args), indent=2, ensure_ascii=False, allow_nan=False))
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    except (Problem, OSError, ValueError) as exc:
        print(f"comfy_3d: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
