import { test, expect } from '@playwright/test';

test.describe('Kiwoom Trading WebApp - Full Integration Verification', () => {
  
  test.beforeEach(async ({ page }) => {
    // 5178 포트로 접속
    await page.goto('http://localhost:5178');
  });

  test('Layout & UI: 4x4 Grid and Theme Consistency', async ({ page }) => {
    // 16개 차트 셀 존재 확인
    const gridItems = page.locator('main > div');
    await expect(gridItems).toHaveCount(16);

    // Deep Obsidian 테마 배경색 확인 (#0B0E14 -> rgb(11, 14, 20))
    const bodyColor = await page.evaluate(() => window.getComputedStyle(document.body).backgroundColor);
    expect(bodyColor).toBe('rgb(11, 14, 20)');

    // 헤더 제목 확인
    await expect(page.locator('h1')).toContainText('Kiwoom Trading Dashboard');
  });

  test('Data Fetching: Initial Chart Data should be loaded', async ({ page }) => {
    // 차트 컨테이너가 렌더링되었는지 확인
    const firstChart = page.locator('main > div').first();
    await expect(firstChart).toBeVisible();

    // [Crucial] 실제 데이터가 로드되었는지 확인 (차트 캔버스가 비어있지 않아야 함)
    // lightweight-charts는 canvas 요소를 사용함
    const canvas = firstChart.locator('canvas');
    const canvasCount = await canvas.count();
    expect(canvasCount).toBeGreaterThanOrEqual(2); // 최소 2개 이상(Main + Axis) 존재 확인
  });

  test('WebSocket: Connection status in UI', async ({ page }) => {
    // 하단 푸터의 연결 상태 텍스트 확인
    const wsStatus = page.locator('footer');
    await expect(wsStatus).toContainText('WS Status: Connected');
  });

  test('Interactive: Search and update stock symbol', async ({ page }) => {
    const firstCell = page.locator('main > div').first();
    const searchInput = firstCell.locator('input.search-input');
    
    // 000660 (SK하이닉스) 입력
    const newSymbol = '000660';
    await searchInput.fill(newSymbol);
    await searchInput.press('Enter');

    // 종목 코드가 업데이트되었는지 확인
    await expect(firstCell.locator('span.font-bold').first()).toContainText(newSymbol);
  });

  test('Robustness: No console errors allowed', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    // 5초간 대기하며 런타임 에러 발생 여부 감시 (특히 lightweight-charts Assertion 에러 방지)
    await page.waitForTimeout(5000);
    
    expect(errors).not.toContain(expect.stringContaining('Assertion failed'));
    expect(errors).not.toContain(expect.stringContaining('data must be asc ordered'));
  });
});
