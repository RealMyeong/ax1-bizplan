// Optional calculation-engine regression. Run in a workspace with @oai/artifact-tool.
// Never exports a workbook or changes the supplied template.
import assert from 'node:assert/strict';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';

const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(process.argv[2]));
const budget = wb.worksheets.getItem('02_승인예산');
const ledger = wb.worksheets.getItem('01_구매비용원장');
budget.getRange('A7:G7').values = [['B-TEST-01', '연구재료비', '재료구매', '합성 시험예산', 10000, 10, 100000]];
for (const [address, value] of Object.entries({A7:'TEST-001', B7:'검토중', F7:'B-TEST-01', O7:2, Q7:10000, S7:'포함'})) {
  ledger.getRange(address).values = [[value]];
}
let passed = 0;
function expect(sheet, address, expected) {
  assert.equal(sheet.getRange(address).values[0][0], expected, `${sheet.name}!${address}`);
  passed++;
}
wb.recalculate();
expect(ledger, 'R7', 20000);
expect(ledger, 'AB7', 20000);
expect(budget, 'H7', 20000);
expect(budget, 'M7', 80000);
ledger.getRange('S7').values = [['별도']];
wb.recalculate();
expect(ledger, 'R7', 22000);
ledger.getRange('T7').values = [[21000]];
wb.recalculate();
expect(ledger, 'AB7', 21000);
ledger.getRange('U7').values = [[20500]];
wb.recalculate();
expect(ledger, 'AB7', 20500);
ledger.getRange('W7:X7').values = [[2, 9000]];
wb.recalculate();
expect(ledger, 'Y7', 19800);
expect(ledger, 'AB7', 19800);
expect(budget, 'J7', 19800);
ledger.getRange('AC7:AE7').values = [[18000, 1800, -800]];
wb.recalculate();
expect(ledger, 'AF7', 19000);
expect(ledger, 'AH7', 800);
expect(budget, 'O7', 81000);
ledger.getRange('C7').values = [['제외']];
wb.recalculate();
expect(ledger, 'AB7', 0);
expect(budget, 'I7', 0);
ledger.getRange('C7').values = [['포함']];
ledger.getRange('B7').values = [['취소']];
wb.recalculate();
expect(ledger, 'AB7', 0);
console.log(`PASS: ${passed} synthetic formula assertions; no workbook exported`);
