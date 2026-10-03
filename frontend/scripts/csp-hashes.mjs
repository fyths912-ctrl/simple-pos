/**
 * ビルド後処理：静的出力（out/）の HTML に含まれるインライン <script> の SHA-256 を集め、
 * staticwebapp.config.json の CSP の script-src に追加したものを out/ に書き出す。
 * これで本番 CSP に 'unsafe-inline' を入れずに済む（設計10.1／T-059）。
 */
import { createHash } from "node:crypto";
import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const OUT = "out";

function htmlFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return htmlFiles(p);
    return p.endsWith(".html") ? [p] : [];
  });
}

const hashes = new Set();
const inline = /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g;
for (const file of htmlFiles(OUT)) {
  for (const m of readFileSync(file, "utf8").matchAll(inline)) {
    if (m[1].length === 0) continue;
    hashes.add(`'sha256-${createHash("sha256").update(m[1], "utf8").digest("base64")}'`);
  }
}

const config = JSON.parse(readFileSync("staticwebapp.config.json", "utf8"));
const csp = config.globalHeaders["Content-Security-Policy"];
const scriptSrc = `script-src 'self' ${[...hashes].sort().join(" ")}`.trim();
config.globalHeaders["Content-Security-Policy"] = csp.replace(/default-src 'self';/, `default-src 'self'; ${scriptSrc};`);
writeFileSync(join(OUT, "staticwebapp.config.json"), JSON.stringify(config, null, 2));
console.log(`csp-hashes: ${hashes.size} 件のインライン script を許可リストに追加しました`);
