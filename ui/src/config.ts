// Base URL for data files. Override with VITE_DATA_BASE_URL env var.
// In production, set to GCS public bucket URL, e.g.:
//   https://storage.googleapis.com/my-bucket
export const DATA_BASE_URL: string =
  import.meta.env.VITE_DATA_BASE_URL?.replace(/\/$/, "") ?? "";

export function dataUrl(path: string): string {
  return `${DATA_BASE_URL}/${path}`;
}
