const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });

  console.log('=== Loading PRODUCTION map page ===');
  await page.goto('https://immo-agent-vienna.vercel.app/dashboard/map', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(5000);

  console.log('\n=== TEST 1: Click sidebar listing ===');
  // The sidebar listing cards have class with "flex gap-3 bg-white rounded-lg"
  const sidebarCards = page.locator('[class*="rounded-lg"][class*="bg-white"][class*="cursor-pointer"]');
  const cardCount = await sidebarCards.count();
  console.log('Sidebar cards found:', cardCount);

  if (cardCount > 0) {
    await sidebarCards.first().click();
    await page.waitForTimeout(2000);
    const modal1 = await page.locator('.fixed.inset-0.z-50').count();
    console.log('Modal opened from sidebar click:', modal1 > 0);
  }

  console.log('\n=== TEST 2: Close modal ===');
  await page.locator('.fixed.inset-0.z-50 button').first().click();
  await page.waitForTimeout(2000);
  const modalClosed = await page.locator('.fixed.inset-0.z-50').count();
  console.log('Modal closed:', modalClosed === 0);

  console.log('\n=== TEST 3: Click sidebar listing AGAIN ===');
  await sidebarCards.first().click();
  await page.waitForTimeout(2000);
  const modal2 = await page.locator('.fixed.inset-0.z-50').count();
  console.log('Modal opened on 2nd sidebar click:', modal2 > 0);

  console.log('\n=== TEST 4: Close, then click map marker ===');
  await page.locator('.fixed.inset-0.z-50 button').first().click();
  await page.waitForTimeout(2000);
  const m1 = await page.locator('.leaflet-marker-icon').first().boundingBox();
  await page.mouse.click(m1.x + 5, m1.y + 5);
  await page.waitForTimeout(2000);
  const modal3 = await page.locator('.fixed.inset-0.z-50').count();
  console.log('Modal opened from map marker:', modal3 > 0);

  console.log('\n=== Console errors ===');
  errors.forEach(e => console.log('ERROR:', e.substring(0, 200)));

  await browser.close();
  console.log('\n=== DONE ===');
})().catch(e => { console.error('Test failed:', e.message); process.exit(1); });
