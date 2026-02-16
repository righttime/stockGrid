import { test, expect } from '@playwright/test';

test.describe('Kiwoom Trading Dashboard Functional Check', () => {
  test.beforeEach(async ({ page }) => {
    // ?„ë¡ ?¸ì—”???‘ì† (Vite ê¸°ë³¸ ?¬íŠ¸)
    await page.goto('http://localhost:4173');
  });

  test('UI Layout: Should display 4x4 grid (16 charts)', async ({ page }) => {
    const gridItems = page.locator('main > div');
    await expect(gridItems).toHaveCount(16);
    
    // ?¤ë” ?íƒœ ?•ì¸
    await expect(page.locator('header')).toContainText('Kiwoom Trading Dashboard');
    await expect(page.locator('header')).toContainText('API Connected');
  });

  test('Interactive: Should update stock symbol via search', async ({ page }) => {
    // ì²?ë²ˆì§¸ ì°¨íŠ¸ ?€??ê²€?‰ì°½ ì°¾ê¸°
    const firstCell = page.locator('main > div').first();
    const searchInput = firstCell.locator('input[placeholder*="Symbol"]');
    
    // ?ˆë¡œ??ì¢…ëª© ì½”ë“œ ?…ë ¥ (?? SK?˜ì´?‰ìŠ¤ 000660)
    const newSymbol = '000660';
    await searchInput.fill(newSymbol);
    await searchInput.press('Enter');

    // ?´ë‹¹ ?€??ì¢…ëª©ëª…ì´ ë³€ê²½ë˜?ˆëŠ”ì§€ ?•ì¸
    await expect(firstCell.locator('span').first()).toContainText(newSymbol);
  });

  test('Performance: Monitor for browser console errors', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    // 5ì´ˆê°„ ?€ê¸°í•˜ë©??¤ì‹œê°??°ì´??? ì… ???ëŸ¬ ë°œìƒ ?¬ë? ì²´í¬
    await page.waitForTimeout(5000);
    
    expect(errors).toHaveLength(0);
  });

  test('WebSocket: Check connection status in UI', async ({ page }) => {
    // ?¸í„°??WS ?°ê²° ?íƒœ ?ìŠ¤???•ì¸
    const footer = page.locator('footer');
    await expect(footer).toContainText('WS Status: Connected');
  });
});
