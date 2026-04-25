const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  const consoleMessages = [];
  page.on('console', msg => {
    if (msg.type() === 'error' || msg.type() === 'log') {
      consoleMessages.push({ type: msg.type(), text: msg.text() });
    }
  });

  console.log('=== Loading map page ===');
  await page.goto('http://localhost:3001/dashboard/map', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(5000);

  console.log('\n=== Checking initial state ===');
  const markers = await page.locator('.leaflet-marker-icon').count();
  console.log('Markers on map:', markers);

  const listings = await page.locator('text=LISTINGS').textContent();
  console.log('Sidebar listings text:', listings);

  if (markers === 0) {
    console.log('\nNo markers loaded! Checking for errors...');
    consoleMessages.filter(m => m.type === 'error').forEach(m => console.log('ERROR:', m.text.substring(0, 200)));
  }

  console.log('\n=== Trying to click a marker ===');
  if (markers > 0) {
    const markerBox = await page.locator('.leaflet-marker-icon').first().boundingBox();
    console.log('Marker position:', JSON.stringify(markerBox));
    
    // Try page.mouse.click which bypasses strict mode
    await page.mouse.click(markerBox.x + 5, markerBox.y + 5);
    await page.waitForTimeout(2000);

    const modalAfterClick = await page.locator('.fixed.inset-0.z-50').count();
    console.log('Modal opened after click:', modalAfterClick > 0);

    // Check if popup appeared instead
    const popupVisible = await page.locator('.leaflet-popup').count();
    console.log('Popup appeared:', popupVisible > 0);

    // Check console logs
    console.log('\n=== Console logs ===');
    consoleMessages.forEach(m => console.log(`[${m.type}] ${m.text.substring(0, 150)}`));
  }

  await browser.close();
  console.log('\n=== DONE ===');
})().catch(e => { console.error('Test failed:', e.message); process.exit(1); });
