import { test, expect } from '@playwright/test';

test.describe('Tailwind CSS Verification', () => {
  test('Theme: Should apply custom background color to body', async ({ page }) => {
    await page.goto('http://localhost:4173');
    
    // body??ë°°ê²½?‰ì´ tailwind.config.js???•ì˜??#0F172A (rgb(15, 23, 42))?¸ì? ?•ì¸
    const bodyColor = await page.evaluate(() => {
      return window.getComputedStyle(document.body).backgroundColor;
    });
    expect(bodyColor).toBe('rgb(15, 23, 42)');
  });

  test('Grid: Should apply grid-cols-4 layout', async ({ page }) => {
    await page.goto('http://localhost:4173');
    
    const mainGrid = page.locator('main');
    
    // ê·¸ë¦¬??ì»¨í…Œ?´ë„ˆ??display ?ì„±??grid?¸ì? ?•ì¸
    const display = await mainGrid.evaluate(el => window.getComputedStyle(el).display);
    expect(display).toBe('grid');

    // ê·¸ë¦¬??ì»¬ëŸ¼??4ê°œë¡œ ë¶„í• ?˜ì–´ ?ˆëŠ”ì§€ ?•ì¸ (computed style??grid-template-columns)
    const gridColumns = await mainGrid.evaluate(el => window.getComputedStyle(el).gridTemplateColumns);
    const columns = gridColumns.split(' ');
    expect(columns).toHaveLength(4);
  });

  test('Utility: Should apply surface color to chart cards', async ({ page }) => {
    await page.goto('http://localhost:4173');
    
    // ì°¨íŠ¸ ì¹´ë“œ??ë°°ê²½?‰ì´ #1E293B (rgb(30, 41, 59))?¸ì? ?•ì¸
    const firstCard = page.locator('main > div').first();
    const cardColor = await firstCard.evaluate(el => window.getComputedStyle(el).backgroundColor);
    expect(cardColor).toBe('rgb(30, 41, 59)');
  });
});
