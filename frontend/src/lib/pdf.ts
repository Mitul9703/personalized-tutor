import html2canvas from "html2canvas";
import { jsPDF } from "jspdf";

// Turns an off-screen layout into a downloaded PDF. We capture each block (a
// slide, a section, a card, a question) on its own with html2canvas, so the
// PDF uses the exact same rendered DOM, colours, and diagrams as the app, and
// then flow the block images onto A4 pages without ever cutting a block in two.
// Slides get one page each; the other types flow and start a new page when the
// next block would not fit.

function sanitize(name: string): string {
  return (name || "tutorial").replace(/[^\w.-]+/g, "_").slice(0, 80);
}

// wait until every Visual has finished rendering (mermaid renders async and
// shows a "rendering diagram…" placeholder until it is done).
async function waitForVisuals(el: HTMLElement, timeout = 5000): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    if (!el.textContent?.includes("rendering diagram")) return;
    await new Promise((r) => setTimeout(r, 120));
  }
}

export async function exportBlocksPdf(
  container: HTMLElement,
  title: string,
  opts: { slideMode?: boolean } = {},
): Promise<void> {
  await waitForVisuals(container);
  // let fonts (KaTeX) settle so the capture has the right glyphs
  if ((document as any).fonts?.ready) await (document as any).fonts.ready;

  const blocks = Array.from(container.querySelectorAll<HTMLElement>(".pdf-block"));
  // slides print like a real deck: landscape, one slide filling each page.
  const slide = !!opts.slideMode;
  const pdf = new jsPDF({ unit: "pt", format: "a4", orientation: slide ? "landscape" : "portrait" });
  const pageW = pdf.internal.pageSize.getWidth();
  const pageH = pdf.internal.pageSize.getHeight();
  const margin = slide ? 18 : 28;
  const usableW = pageW - margin * 2;
  const usableH = pageH - margin * 2;
  const gap = 12;

  let cursorY = margin;
  let firstPage = true;

  const place = (canvas: HTMLCanvasElement) => {
    const img = canvas.toDataURL("image/jpeg", 0.95);
    if (slide) {
      // one slide per page, scaled to fit the whole page and centred
      if (!firstPage) pdf.addPage();
      const s = Math.min(usableW / canvas.width, usableH / canvas.height);
      const w = canvas.width * s;
      const h = canvas.height * s;
      pdf.addImage(img, "JPEG", margin + (usableW - w) / 2, margin + (usableH - h) / 2, w, h);
      firstPage = false;
      return;
    }
    // flow mode: a block taller than a page is scaled to fit, so it is never cut
    let w = usableW;
    let h = (canvas.height * w) / canvas.width;
    if (h > usableH) {
      h = usableH;
      w = (canvas.width * h) / canvas.height;
    }
    if (cursorY + h > pageH - margin && cursorY > margin) {
      pdf.addPage();
      cursorY = margin;
    }
    pdf.addImage(img, "JPEG", margin + (usableW - w) / 2, cursorY, w, h);
    cursorY += h + gap;
  };

  for (const block of blocks) {
    const canvas = await html2canvas(block, {
      scale: 2,
      backgroundColor: "#ffffff",
      useCORS: true,
      logging: false,
    });
    place(canvas);
  }

  pdf.save(`${sanitize(title)}.pdf`);
}
