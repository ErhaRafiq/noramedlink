// The server accepts these types up to 10 MB (backend/services/file_service.py).
export const UPLOAD_ACCEPT = ".pdf,.jpg,.jpeg,.png,.webp";
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

// Large photos are shrunk before upload; smaller ones go as they are, to keep OCR detail.
const SHRINK_ABOVE_BYTES = 4 * 1024 * 1024;
const SHRINK_MAX_SIDE = 2400;

/** Re-encodes a large JPEG/PNG/WEBP photo as a smaller JPEG; returns other files unchanged. */
export async function shrinkLargeImage(file: File): Promise<File> {
  if (!/^image\/(jpeg|png|webp)$/.test(file.type) || file.size <= SHRINK_ABOVE_BYTES) return file;
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, SHRINK_MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const context = canvas.getContext("2d");
    if (!context) return file;
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
    if (!blob || blob.size >= file.size) return file;
    return new File([blob], `${file.name.replace(/\.[^.]+$/, "")}.jpg`, { type: "image/jpeg" });
  } catch {
    return file;
  }
}
