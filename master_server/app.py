from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import os, time, json
from collections import defaultdict

app = FastAPI()

CHUNK_SIZE = 1024 * 1024  # 1MB
NODES = ["../chunk_nodes/node1", "../chunk_nodes/node2", "../chunk_nodes/node3"]

# Ensure node directories exist
for node in NODES:
    os.makedirs(node, exist_ok=True)

# Utility: load metadata.json
def load_metadata():
    if not os.path.exists("metadata.json"):
        with open("metadata.json", "w") as f:
            json.dump({}, f)
    with open("metadata.json", "r") as f:
        return json.load(f)

# Utility: save metadata.json
def save_metadata(metadata):
    with open("metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)


# ---------------------------- UPLOAD ---------------------------- #
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    metadata = load_metadata()

    original_filename = file.filename
    timestamp = int(time.time())
    filename = f"{original_filename}_{timestamp}"

    metadata[filename] = {
        "original_name": original_filename,
        "chunks": []
    }

    i = 0
    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break

        chunk_name = f"{filename}_chunk_{i}"
        nodes_for_chunk = NODES[i % len(NODES):] + NODES[:i % len(NODES)]  # Rotate
        replicas = nodes_for_chunk[:2]  # Two replicas

        for node in replicas:
            chunk_path = os.path.join(node, chunk_name)
            with open(chunk_path, "wb") as f:
                f.write(chunk)
            metadata[filename]["chunks"].append({
                "chunk": chunk_name,
                "node": node
            })

        i += 1

    save_metadata(metadata)

    return {
        "status": "success",
        "uploaded_as": filename,
        "original_name": original_filename,
        "chunks": i
    }


# ---------------------------- DOWNLOAD ---------------------------- #

from datetime import datetime
from fastapi.responses import FileResponse
from collections import defaultdict
from fastapi import HTTPException
import os

from fastapi.responses import JSONResponse

from fastapi.responses import JSONResponse

@app.get("/download/{file_id}")
def download_file(file_id: str):
    metadata = load_metadata()
    if file_id not in metadata:
        raise HTTPException(status_code=404, detail="File not found")

    file_entry = metadata[file_id]
    chunks = file_entry["chunks"]
    original_name = file_entry.get("original_name", "downloaded_file")

    chunk_node_map = defaultdict(list)
    for entry in chunks:
        chunk_node_map[entry["chunk"]].append(entry["node"])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"reconstructed_{timestamp}_{original_name}"
    output_path = os.path.join("static", "downloads", safe_filename)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "wb") as out_file:
        for chunk_id in sorted(chunk_node_map, key=lambda x: int(x.split("_")[-1])):
            found = False
            for node in chunk_node_map[chunk_id]:
                chunk_path = os.path.join(node, chunk_id)
                if os.path.exists(chunk_path):
                    with open(chunk_path, "rb") as chunk_file:
                        out_file.write(chunk_file.read())
                    found = True
                    break
            if not found:
                raise HTTPException(status_code=500, detail=f"Missing chunk: {chunk_id}")

    # ✅ Instead of streaming, return URL
    return JSONResponse({
        "status": "success",
        "download_url": f"/static/downloads/{safe_filename}"
    })


# ---------------------------- LIST FILES ---------------------------- #
@app.get("/files")
def list_files():
    metadata = load_metadata()
    files = []

    for file_id, info in metadata.items():
        files.append({
            "file_id": file_id,
            "original_name": info.get("original_name", "unknown"),
            "num_chunks": len(info.get("chunks", []))
        })

    return {"files": files}


# ---------------------------- DELETE FILE ---------------------------- #
@app.delete("/delete/{file_id}")
def delete_file(file_id: str):
    metadata = load_metadata()

    if file_id not in metadata:
        raise HTTPException(status_code=404, detail="File not found")

    for chunk_info in metadata[file_id]["chunks"]:
        chunk_path = os.path.join(chunk_info["node"], chunk_info["chunk"])
        if os.path.exists(chunk_path):
            os.remove(chunk_path)

    del metadata[file_id]
    save_metadata(metadata)

    return {"status": "deleted", "file_id": file_id}

@app.get("/node-status")
def node_status():
    status = []
    for node in NODES:
        node_info = {
            "node_path": node,
            "exists": os.path.exists(node),
            "is_accessible": os.access(node, os.R_OK | os.W_OK),
            "chunk_count": 0
        }

        if node_info["exists"]:
            try:
                node_info["chunk_count"] = len(os.listdir(node))
            except:
                node_info["chunk_count"] = "error"

        status.append(node_info)

    return {"nodes": status}


#-------------------------HEAL FILE----------
@app.post("/heal/{file_id}")
def heal_file(file_id: str):
    metadata = load_metadata()

    if file_id not in metadata:
        raise HTTPException(status_code=404, detail="File not found")

    chunks = metadata[file_id]["chunks"]
    chunk_map = defaultdict(list)

    for entry in chunks:
        chunk_map[entry["chunk"]].append(entry["node"])

    healed = 0

    for chunk_name, nodes in chunk_map.items():
        existing_node = None
        existing_path: str | None = None

        # ✅ Step 1: Find a good existing replica
        for node in nodes:
            chunk_path = os.path.join(node, chunk_name)
            if os.path.exists(chunk_path):
                existing_node = node
                existing_path = chunk_path
                break

        # ✅ Step 2: Validate existing replica exists
        if not existing_path or not os.path.exists(existing_path):
            continue  # No good source for healing

        # ✅ Step 3: Identify missing replicas
        missing_nodes = [n for n in NODES if not os.path.exists(os.path.join(n, chunk_name))]

        # ✅ Step 4: Heal into missing nodes
        for target_node in missing_nodes:
            if target_node == existing_node:
                continue  # Skip already good one

            target_path = os.path.join(target_node, chunk_name)
            try:
                with open(existing_path, "rb") as src, open(target_path, "wb") as dst:
                    dst.write(src.read())
            except Exception as e:
                print(f"Error healing chunk {chunk_name} to {target_node}: {e}")
                continue

            # Avoid duplicate metadata entries
            if not any(c["chunk"] == chunk_name and c["node"] == target_node for c in metadata[file_id]["chunks"]):
                metadata[file_id]["chunks"].append({
                    "chunk": chunk_name,
                    "node": target_node
                })

            healed += 1

    save_metadata(metadata)
    return {"status": "success", "healed_chunks": healed}

#------------UI-----------------
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request



app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/")
def homepage(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

