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

  const markers = await page.locator('.leaflet-marker-icon').count();
  console.log('Markers:', markers);

  console.log('\n=== TEST 1: Click marker 1 ===');
  const m1 = await page.locator('.leaflet-marker-icon').first().boundingBox();
  await page.mouse.click(m1.x + 5, m1.y + 5);
  await page.waitForTimeout(2000);
  const modal1 = await page.locator('.fixed.inset-0.z-50').count();
  console.log('Modal 1 open:', modal1 > 0);

  console.log('\n=== TEST 2: Close modal ===');
  await page.locator('.fixed.inset-0.z-50 button').first().click();
  await page.waitForTimeout(2000);
  const modalClosed = await page.locator('.fixed.inset-0.z-50').count();
  console.log('Modal closed:', modalClosed === 0);

  console.log('\n=== TEST 3: Click SAME marker again ===');
  const m1Again = await page.locator('.leaflet-marker-icon').first().boundingBox();
  await page.mouse.click(m1Again.x + 5, m1Again.y + 5);
  await page.waitForTimeout(2000);
  const modal2 = await page.locator('.fixed.inset-0.z-50').count();
  console.log('Modal opened on same marker:', modal2 > 0);

  console.log('\n=== TEST 4: Close and click DIFFERENT marker ===');
  await page.locator('.fixed.inset-0.z-50 button').first().click();
  await page.waitForTimeout(2000);
  const m2 = await page.locator('.leaflet-marker-icon').nth(5).boundingBox();
  await page.mouse.click(m2.x + 5, m2.y + 5);
  await page.waitForTimeout(2000);
  const modal3 = await page.locator('.fixed.inset-0.z-50').count();
  console.log('Modal opened on different marker:', modal3 > 0);

  console.log('\n=== TEST 5: Close and try sidebar click ===');
  await page.locator('.fixed.inset-0.z-50 button').first().click();
  await page.waitForTimeout(2000);
  const sidebarCard = await page.locator('.flex.flex-col.gap-1.5 > div').first();
  await sidebarCard.click();
  await page.waitForTimeout(2000);
  const modalFromSidebar = await page.locator('.fixed.inset-0.z-50').count();
  console.log('Modal opened from sidebar:', modalFromSidebar > 0);

  console.log('\n=== Console errors ===');
  errors.forEach(e => console.log('ERROR:', e.substring(0, 200)));

  await browser.close();
  console.log('\n=== DONE ===');
})().catch(e => { console.error('Test failed:', e.message); process.exit(1); });
