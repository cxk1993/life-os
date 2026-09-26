/**
 * 杂物库纯函数判据（V1-EXT2 二期）：listTopLevel 排序与图片识别。
 * showDirectoryPicker/handle 体系 jsdom 不可达——这里用内存 mock 迭代器。
 */
import { describe, expect, it } from "vitest";

import { listTopLevel } from "./miscFolder";

function fakeDir(entries: Array<[string, "file" | "directory"]>) {
  const map = new Map(
    entries.map(([name, kind]) => [
      name,
      kind === "file"
        ? ({ kind: "file", name, getFile: async () => new Blob() })
        : ({ kind: "directory", name }),
    ]),
  );
  return {
    name: "杂物",
    kind: "directory",
    async *[Symbol.asyncIterator]() {
      for (const [name, handle] of map) yield [name, handle] as [string, FileSystemHandle];
    },
    queryPermission: async () => "granted",
  } as unknown as Parameters<typeof listTopLevel>[0];
}

describe("miscFolder（杂物库 MVP）", () => {
  it("listTopLevel：目录前、文件后，各自按名排序", async () => {
    const rows = await listTopLevel(
      fakeDir([
        ["b.png", "file"],
        ["子目录", "directory"],
        ["a.png", "file"],
        ["归档", "directory"],
      ]),
    );
    expect(rows.map((r) => r.name)).toEqual(["归档", "子目录", "a.png", "b.png"]);
    expect(rows[0].kind).toBe("directory");
    expect(rows[2].isImage).toBe(true);
  });

  it("图片识别：png/jpg/webp/svg 是图，txt/pdf 不是", async () => {
    const rows = await listTopLevel(
      fakeDir([
        ["a.PNG", "file"],
        ["b.jpeg", "file"],
        ["c.webp", "file"],
        ["d.svg", "file"],
        ["e.txt", "file"],
        ["f.pdf", "file"],
      ]),
    );
    const byName = Object.fromEntries(rows.map((r) => [r.name, r.isImage]));
    expect(byName["a.PNG"]).toBe(true); // 大写扩展名也识别
    expect(byName["b.jpeg"]).toBe(true);
    expect(byName["c.webp"]).toBe(true);
    expect(byName["d.svg"]).toBe(true);
    expect(byName["e.txt"]).toBe(false);
    expect(byName["f.pdf"]).toBe(false);
  });

  it("空目录返回空列表不抛错", async () => {
    const rows = await listTopLevel(fakeDir([]));
    expect(rows).toEqual([]);
  });
});
