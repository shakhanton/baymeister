/**
 * Генерує типи з усіх контрактів у contracts/.
 *
 * Запускається в CI після мерджу контракту. Результат комітиться — так
 * фронтенд-модуль отримує типи, не піднімаючи бекенд.
 */
import { execFileSync } from 'node:child_process';
import { mkdirSync, readdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const contractsDir = resolve(here, '../../../contracts');
const outDir = resolve(here, '../src/generated');

mkdirSync(outDir, { recursive: true });

const contracts = readdirSync(contractsDir).filter((f) => f.endsWith('.yaml'));

if (contracts.length === 0) {
  console.error('У contracts/ немає жодного .yaml');
  process.exit(1);
}

for (const file of contracts) {
  const name = file.replace(/\.yaml$/, '');
  const out = join(outDir, `${name}.ts`);
  console.log(`${file} → src/generated/${name}.ts`);
  execFileSync(
    'npx',
    ['openapi-typescript', join(contractsDir, file), '-o', out],
    { stdio: 'inherit' },
  );
}

console.log(`Згенеровано контрактів: ${contracts.length}`);
