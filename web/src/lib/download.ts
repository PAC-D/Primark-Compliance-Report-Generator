"use client";

import { useState } from "react";
import { toast } from "sonner";
import { BASE, errorText } from "./api";

/** The file name in a Content-Disposition header (RFC 6266: filename* wins over filename), or null. */
function headerName(cd: string | null): string | null {
  if (!cd) return null;
  const star = /filename\*\s*=\s*[^']*'[^']*'([^;]+)/i.exec(cd);
  if (star) {
    try {
      return decodeURIComponent(star[1].trim());
    } catch {}
  }
  const plain = /filename\s*=\s*(?:"([^"]*)"|([^;]+))/i.exec(cd);
  return plain ? (plain[1] ?? plain[2]).trim() : null;
}

/** Fetches a file as a blob and saves it, so the caller knows when it has arrived. Throws Error(the API's message). */
/** A root-relative URL gets the app's base path ("/api/x" → "/compliance/api/x"), so callers can't forget it. */
const withBase = (url: string): string => (url.startsWith("/") && !url.startsWith(`${BASE}/`) ? BASE + url : url);

export async function downloadFile(url: string, fallbackName: string): Promise<void> {
  const res = await fetch(withBase(url), { cache: "no-store" });
  if (!res.ok) throw new Error(await errorText(res));
  const blob = await res.blob();
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = headerName(res.headers.get("Content-Disposition")) || fallbackName;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 1000); // the click has handed the blob to the browser by then
}

/** A download button's state: start(url, name) fetches and saves the file, toasting the result; busy while it runs. */
export function useDownload() {
  const [busy, setBusy] = useState(false);
  const start = async (url: string, name: string) => {
    setBusy(true);
    try {
      await downloadFile(url, name);
      toast.success("Downloaded", { description: name });
    } catch (e) {
      toast.error("Download failed", { description: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
    }
  };
  return { start, busy };
}
