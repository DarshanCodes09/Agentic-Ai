import { apiClient } from "./client";

export async function downloadOrPreviewFile(
  endpoint: string,
  fallbackFilename: string = "download",
  inline: boolean = false
): Promise<void> {
  const response = await apiClient.get(endpoint, {
    params: { inline },
    responseType: "blob",
  });

  const contentType = String(response.headers["content-type"] || "application/octet-stream");
  const blob = new Blob([response.data], { type: contentType });

  const blobUrl = window.URL.createObjectURL(blob);

  if (inline) {
    window.open(blobUrl, "_blank");
  } else {
    const link = document.createElement("a");
    link.href = blobUrl;
    link.download = fallbackFilename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(blobUrl);
  }
}
