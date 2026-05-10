import fs from "node:fs/promises";
import path from "node:path";

function uploadRoot() {
  return path.resolve(process.cwd(), "public", "uploads");
}

export function resolveLocalReportPath(fileUrl: string) {
  let pathname = fileUrl;

  try {
    pathname = new URL(fileUrl, "http://local").pathname;
  } catch {
    pathname = fileUrl;
  }

  const normalized = decodeURIComponent(pathname).replace(/\\/g, "/");
  if (!normalized.startsWith("/uploads/")) {
    return null;
  }

  const resolved = path.resolve(process.cwd(), "public", `.${normalized}`);
  const root = uploadRoot();
  if (resolved !== root && !resolved.startsWith(`${root}${path.sep}`)) {
    return null;
  }

  return resolved;
}

export async function readReportFileBuffer(fileUrl: string) {
  const localPath = resolveLocalReportPath(fileUrl);
  if (localPath) {
    return fs.readFile(localPath);
  }

  const response = await fetch(fileUrl);
  if (!response.ok) {
    throw new Error(`Unable to read uploaded report file (${response.status}).`);
  }

  return Buffer.from(await response.arrayBuffer());
}

export async function deleteLocalReportFile(fileUrl: string) {
  const localPath = resolveLocalReportPath(fileUrl);
  if (!localPath) {
    return;
  }

  await fs.unlink(localPath).catch(() => null);
}
