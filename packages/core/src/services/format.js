function formatDateTime(dt) {
  if (!dt) return "";
  const d = dt instanceof Date ? dt : new Date(dt);
  if (Number.isNaN(d.getTime())) return "";

  const pad = (n) => String(n).padStart(2, "0");
  return [
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`,
  ].join(" ");
}

function firstAddress(list) {
  if (!list) return "";
  const arr = Array.isArray(list) ? list : [list];
  for (const item of arr) {
    if (!item) continue;
    if (typeof item === "string") return item;
    if (item.address) return item.address;
    if (item.name && item.address) return `${item.name} <${item.address}>`;
  }
  return "";
}

function hasAttachmentsFromBodyStructure(node) {
  if (!node || typeof node !== "object") return false;

  const disp = (node.disposition || "").toLowerCase();
  const params = node.parameters || {};
  if (disp === "attachment") return true;
  if (disp === "inline" && params && params.filename) return true;
  if (params && params.filename) return true;

  const children = node.childNodes || node.childnodes || node.children;
  if (Array.isArray(children)) {
    for (const c of children) {
      if (hasAttachmentsFromBodyStructure(c)) return true;
    }
  }
  return false;
}

function formatSize(bytes) {
  const n = Number(bytes || 0);
  if (!Number.isFinite(n) || n <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"]; 
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  const rounded = i === 0 ? String(Math.round(v)) : v.toFixed(1);
  return `${rounded} ${units[i]}`;
}

module.exports = {
  formatDateTime,
  firstAddress,
  hasAttachmentsFromBodyStructure,
  formatSize,
};
