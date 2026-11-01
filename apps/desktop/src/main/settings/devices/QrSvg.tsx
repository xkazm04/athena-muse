// The phone's pairing address as a QR picture (portable ADR 0140). The encoder is qr.ts; this file
// only draws its matrix.
//
// One <path> of dark modules on one paper <rect>, with the four-module quiet zone the standard asks
// for, `shape-rendering: crispEdges`, and each run of dark modules along a row merged into one
// rectangle. The colours are the stylesheet's: dark on light in both themes, because a phone camera
// reads light-on-dark codes badly or not at all.
//
// The text is a claim credential (the pairing id and its nonce). It goes into the encoder and nowhere
// else: not into the accessible name, not into a title, not into a log. When the encoder cannot draw
// it (too long for version 10) `qrPicture` answers `null` and the caller shows the code alone.

import { qrMatrix } from "./qr";

/** The light margin around the code, in modules (ISO/IEC 18004 asks for four). */
export const QUIET = 4;

/** A drawn code: its side in modules, quiet zone included, and the dark modules as one path. */
export interface QrPicture {
  size: number;
  path: string;
}

/** The picture of `text`, or `null` when the encoder cannot hold it. Never throws, never logs. */
export function qrPicture(text: string): QrPicture | null {
  let matrix: boolean[][];
  try {
    matrix = qrMatrix(text);
  } catch {
    return null;
  }
  const n = matrix.length;
  if (n === 0) return null;
  let path = "";
  matrix.forEach((row, y) => {
    let x = 0;
    while (x < n) {
      if (!row[x]) {
        x += 1;
        continue;
      }
      let run = 1;
      while (x + run < n && row[x + run]) run += 1;
      path += `M${x + QUIET} ${y + QUIET}h${run}v1h-${run}z`;
      x += run;
    }
  });
  return { size: n + 2 * QUIET, path };
}

/** The picture itself. `label` is its accessible name: what it is for, never what it says. */
export function QrSvg({ picture, label }: { picture: QrPicture; label: string }) {
  const { size, path } = picture;
  return (
    <svg className="m-qr" viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label} shapeRendering="crispEdges">
      <rect className="m-qr__paper" width={size} height={size} />
      <path className="m-qr__ink" d={path} />
    </svg>
  );
}
