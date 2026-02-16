import { test, expect } from '@playwright/test';

test.describe('Trading Dashboard E2E', () => {
  test('should render 4x4 grid and stock charts', async ({ page }) => {
    // 개발 ?�버가 ?�행 중이?�고 가??(?�트??Vite 기본�?4173)
    await page.goto('http://localhost:4173');

    // ?�?��? ?�인
    await expect(page.locator('h1')).toContainText('Kiwoom Trading Dashboard');

    // 16개의 종목 카드가 ?�는지 ?�인
    const charts = page.locator('main > div');
    await expect(charts).toHaveCount(16);

    // �?번째 종목 코드 ?�인
    await expect(charts.first().locator('span').first()).toContainText('005930');

    // 콘솔 ?�러 모니?�링
    page.on('console', msg => {
      if (msg.type() === 'error') {
        console.error(`Browser Error: ${msg.text()}`);
      }
    });
  });
});
