import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Prose } from "./Prose";

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), "utf8");

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Prose, the one door", () => {
  it("renders each construct of the subset as its element", () => {
    const { container } = render(
      <Prose text={"Hi **you** and *them*, run `ls`.\nNext line.\n\n- a\n- b\n\n3. c\n4. d\n\n```sh\necho hi\n```"} />,
    );
    expect(screen.getByText("you").tagName).toBe("STRONG");
    expect(screen.getByText("them").tagName).toBe("EM");
    expect(screen.getByText("ls").tagName).toBe("CODE");
    expect(container.querySelector("p br")).toBeTruthy();
    expect(screen.getByText("a").tagName).toBe("LI");
    expect(container.querySelector("ol")!.getAttribute("start")).toBe("3");
    expect(container.querySelector("pre code")!.textContent).toBe("echo hi");
    expect(screen.getByText("sh").className).toBe("prose-code__lang");
  });

  it("renders HTML and script in the text as inert characters", () => {
    const evil =
      '<script>alert(1)</script> <img src=x onerror="alert(2)"> <a href="javascript:alert(3)">x</a> <style>*{display:none}</style>';
    const { container } = render(<Prose text={`${evil}\n\n- <b>bold?</b>\n\n\`\`\`\n<iframe src="x"></iframe>\n\`\`\``} />);
    expect(container.querySelector("script, img, a, style, b, iframe")).toBeNull();
    expect(container.querySelector("p")!.textContent).toBe(evil);
    expect(screen.getByText("<b>bold?</b>").tagName).toBe("LI");
    expect(container.querySelector("pre code")!.textContent).toBe('<iframe src="x"></iframe>');
  });

  it("shows a link's true address beside its words and makes nothing clickable", () => {
    const { container } = render(
      <Prose text={"See [your bank](https://evil.test/login) or [javascript:x](javascript:alert(1)) or [https://a.test](https://a.test)."} />,
    );
    expect(container.querySelector("a")).toBeNull();
    const links = [...container.querySelectorAll(".prose-link")].map((l) => l.textContent);
    expect(links).toEqual(["your bank (https://evil.test/login)", "javascript:x (javascript:alert(1))","https://a.test"]);
  });

  it("copies a code block's source text exactly and says so", async () => {
    const source = '  if (a) {\n\treturn "x\\ty";  \n  }';
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    render(<Prose text={"```js\n" + source + "\n```"} />);
    expect(document.querySelector("pre code")!.textContent).toBe(source);
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Copy" })));
    expect(writeText).toHaveBeenCalledWith(source);
    expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy();
  });

  it("says so when there is no clipboard, never a press that does nothing", async () => {
    vi.stubGlobal("navigator", {});
    render(<Prose text={"```\nx\n```"} />);
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Copy" })));
    expect(screen.getByRole("button", { name: "Could not copy" })).toBeTruthy();
  });

  it("renders a streaming prefix stably: an open fence is a code block, an open ** is bold, no marker shows", () => {
    const { container, rerender } = render(<Prose live text={"Try:\n\n```py\nprint("} />);
    const pre = container.querySelector("pre")!;
    expect(pre.textContent).toBe("print(");
    rerender(<Prose live text={'Try:\n\n```py\nprint("hi")\n```\n\nThen **chec'} />);
    expect(container.querySelector("pre")).toBe(pre);
    expect(pre.textContent).toBe('print("hi")');
    expect(container.querySelector("strong")!.textContent).toBe("chec");
    expect(container.textContent).not.toContain("*");
    rerender(<Prose live text={'Try:\n\n```py\nprint("hi")\n```\n\nThen **check** it'} />);
    expect(container.querySelector("strong")!.textContent).toBe("check");
  });

  it("reads unmatched markers literally once the text is settled", () => {
    const { container } = render(<Prose text={"a **b and `c"} />);
    expect(container.querySelector("strong, code")).toBeNull();
    expect(container.textContent).toBe("a **b and `c");
  });

  it("fades in only the newest words, never again the words already shown, and none once settled", () => {
    const { container, rerender } = render(<Prose live text="By April" marks={[0]} />);
    const first = container.querySelector(".prose-new")!;
    expect(first.textContent).toBe("By April");
    rerender(<Prose live text="By April 15." marks={[0, 8]} />);
    const spans = [...container.querySelectorAll(".prose-new")];
    expect(spans.map((s) => s.textContent)).toEqual(["By April ", "15."]);
    expect(spans[0]).toBe(first); // the same node: mounted once, animated once
    rerender(<Prose text="By April 15." />);
    expect(container.querySelector(".prose-new")).toBeNull();
    expect(container.querySelector("p")!.textContent).toBe("By April 15.");
  });

  it("does not re-render a settled block as the tail grows", () => {
    const { container, rerender } = render(<Prose live text={"First.\n\nSecond"} marks={[0, 8]} />);
    const firstP = container.querySelector("p")!;
    const html = firstP.innerHTML;
    rerender(<Prose live text={"First.\n\nSecond and third"} marks={[0, 8, 14]} />);
    expect(container.querySelector("p")).toBe(firstP);
    expect(firstP.innerHTML).toBe(html);
  });

  it("stills the reveal under calm and reduced motion, within 150 ms otherwise", () => {
    const css = read("./prose.css");
    expect(css).toMatch(/\.prose-new \{\s*animation: prose-reveal var\(--dur-fast\)/);
    expect(css).toMatch(/:root\[data-motion="calm"\] \.prose-new \{\s*animation: none;/);
    expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\) \{\s*\.prose-new \{\s*animation: none;/);
    const fast = Number(/--dur-fast: (\d+)ms/.exec(read("../theme/tokens.css"))![1]);
    expect(fast).toBeLessThanOrEqual(150);
  });
});
