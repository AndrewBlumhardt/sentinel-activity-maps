// TSV delimiter is a TAB character.
// Keep this tiny and predictable for contributors.
export function parseTSV(text) {
  const normalized = text.replace(/\r\n/g, "\n").trim();
  const lines = normalized.split("\n").filter(Boolean);

  const headers = lines.shift().split("\t").map(h => h.trim());

  return lines.map(line => {
    const values = line.split("\t");
    const row = {};
    headers.forEach((h, i) => {
      row[h] = (values[i] || "").trim();
    });
    return row;
  });
}
