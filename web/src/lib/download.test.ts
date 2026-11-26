import { afterEach, describe, expect, it, vi } from "vitest";
import { downloadFile } from "./download";

function stubDom() {
  const a = { href: "", download: "", click: vi.fn(), remove: vi.fn() };
  vi.stubGlobal("document", { createElement: () => a, body: { append: vi.fn() } });
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:x", revokeObjectURL: vi.fn() }));
  return a;
}

describe("downloadFile", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("adds the base path to a root-relative URL, once", async () => {
    stubDom();
    const f = vi.fn(async () => new Response("pdf"));
    vi.stubGlobal("fetch", f);
    await downloadFile("/api/supplier-pdf?month=2026-10", "x.pdf");
    await downloadFile("/compliance/api/x", "x.pdf");
    expect(f.mock.calls.map((c) => (c as unknown[])[0])).toEqual(["/compliance/api/supplier-pdf?month=2026-10", "/compliance/api/x"]);
  });

  it("rejects with the API's error", async () => {
    stubDom();
    vi.stubGlobal("fetch", async () => new Response('{"error":"No data"}', { status: 404 }));
    await expect(downloadFile("/x", "x.pdf")).rejects.toThrow("No data");
  });

  it("saves under the name from Content-Disposition", async () => {
    const a = stubDom();
    vi.stubGlobal("fetch", async () =>
      new Response("pdf", { headers: { "Content-Disposition": 'attachment; filename="A & B.pdf"' } }));
    await downloadFile("/x", "fallback.pdf");
    expect(a.download).toBe("A & B.pdf");
    expect(a.click).toHaveBeenCalledOnce();
  });

  it("falls back to the given name, and reads a UTF-8 filename*", async () => {
    const a = stubDom();
    vi.stubGlobal("fetch", async () => new Response("pdf"));
    await downloadFile("/x", "fallback.pdf");
    expect(a.download).toBe("fallback.pdf");
    vi.stubGlobal("fetch", async () =>
      new Response("pdf", { headers: { "Content-Disposition": "attachment; filename*=utf-8''Caf%C3%A9.zip" } }));
    await downloadFile("/x", "fallback.pdf");
    expect(a.download).toBe("Café.zip");
  });
});
