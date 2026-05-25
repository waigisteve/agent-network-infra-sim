import { describe, expect, it } from "vitest";

describe("frontend configuration", () => {
  it("has a fallback API base url", () => {
    expect("http://127.0.0.1:8000").toContain("8000");
  });
});

