/**
 * RFC 822 multipart/alternative builder.
 *
 * EditionStories.tsx and VcIssueExport.tsx both built .eml files with
 * identical scaffolding (different subject + body). One implementation
 * here, downloaded as <filename>.eml — opening it in Apple Mail / Spark
 * loads the formatted HTML 1:1, no clipboard-paste normalization in the
 * way.
 */

export function buildEml(opts: {
  subject: string;
  plainText: string;
  html: string;
}): string {
  const boundary = `=_lede_${Math.floor(Math.random() * 1e9).toString(36)}`;
  return [
    `MIME-Version: 1.0`,
    `Subject: ${opts.subject}`,
    `Content-Type: multipart/alternative; boundary="${boundary}"`,
    ``,
    `--${boundary}`,
    `Content-Type: text/plain; charset=UTF-8`,
    `Content-Transfer-Encoding: 8bit`,
    ``,
    opts.plainText,
    `--${boundary}`,
    `Content-Type: text/html; charset=UTF-8`,
    `Content-Transfer-Encoding: 8bit`,
    ``,
    `<!doctype html><html><body>${opts.html}</body></html>`,
    `--${boundary}--`,
    ``,
  ].join('\r\n');
}

export function downloadEml(opts: {
  filename: string;
  subject: string;
  plainText: string;
  html: string;
}): void {
  const eml = buildEml(opts);
  const blob = new Blob([eml], { type: 'message/rfc822' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = opts.filename;
  a.click();
  URL.revokeObjectURL(url);
}
