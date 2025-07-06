async function fetchFiles() {
  const res = await fetch("/files");
  const data = await res.json();

  const table = document.getElementById("fileTableBody");
  table.innerHTML = "";

 data.files.forEach(file => {
  const row = document.createElement("tr");

  const nameCell = document.createElement("td");
  nameCell.innerText = file.original_name;
  row.appendChild(nameCell);

  const chunksCell = document.createElement("td");
  chunksCell.innerText = file.num_chunks;
  row.appendChild(chunksCell);

  const downloadCell = document.createElement("td");
  const downloadBtn = document.createElement("button");
  downloadBtn.innerText = "Download";
  downloadBtn.onclick = () => downloadFile(file.file_id);
  downloadCell.appendChild(downloadBtn);
  row.appendChild(downloadCell);

  const deleteCell = document.createElement("td");
  const deleteBtn = document.createElement("button");
  deleteBtn.innerText = "Delete";
  deleteBtn.onclick = () => deleteFile(file.file_id);
  deleteCell.appendChild(deleteBtn);
  row.appendChild(deleteCell);

  const healCell = document.createElement("td");
  const healBtn = document.createElement("button");
  healBtn.innerText = "Heal";
  healBtn.onclick = () => healFile(file.file_id);
  healCell.appendChild(healBtn);
  row.appendChild(healCell);

  table.appendChild(row);
});

}

async function uploadFile() {
  const fileInput = document.getElementById("fileInput");
  if (!fileInput.files.length) return alert("Please select a file.");

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  const res = await fetch("/upload", {
    method: "POST",
    body: formData
  });

  const result = await res.json();
  alert(`Upload complete! Stored as: ${result.uploaded_as}`);
  fetchFiles();
}

async function downloadFile(file_id) {
  const res = await fetch(`/download/${file_id}`);
  const result = await res.json();

  if (result.status === "success" && result.download_url) {
    const a = document.createElement("a");
    a.href = result.download_url;
    a.download = ""; // force download with original name
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  } else {
    alert("Download failed");
  }
}




async function deleteFile(file_id) {
  const confirmed = confirm("Are you sure you want to delete this file?");
  if (!confirmed) return;

  const res = await fetch(`/delete/${file_id}`, {
    method: "DELETE"
  });

  const result = await res.json();
  alert(result.status === "deleted" ? "Deleted!" : "Failed");
  fetchFiles();
}

async function fetchNodeStatus() {
  const res = await fetch("/node-status");
  const data = await res.json();

  const table = document.getElementById("nodeStatusTableBody");
  table.innerHTML = "";

  data.nodes.forEach(node => {
    const row = document.createElement("tr");

    const pathCell = document.createElement("td");
    pathCell.innerText = node.node_path;
    row.appendChild(pathCell);

    const statusCell = document.createElement("td");
    statusCell.innerText = node.exists ? "🟢 Online" : "🔴 Offline";
    row.appendChild(statusCell);

    const accessCell = document.createElement("td");
    accessCell.innerText = node.is_accessible ? "✔️ Yes" : "❌ No";
    row.appendChild(accessCell);

    const countCell = document.createElement("td");
    countCell.innerText = node.chunk_count;
    row.appendChild(countCell);

    table.appendChild(row);
  });
}

async function healFile(file_id) {
  const res = await fetch(`/heal/${file_id}`, {
    method: "POST"
  });
  const result = await res.json();
  alert(`Healed ${result.healed_chunks} chunks`);
  fetchFiles();
}



window.onload = () => {
  fetchFiles();
  fetchNodeStatus();
};

