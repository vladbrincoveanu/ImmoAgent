const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  const consoleMessages = [];
  page.on('console', msg => {
    consoleMessages.push({ type: msg.type(), text: msg.text() });
  });

  console.log('=== Loading PRODUCTION map page ===');
  await page.goto('https://immo-agent-vienna.vercel.app/dashboard/map', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(5000);

  console.log('\n=== Checking initial state ===');
  const markers = await page.locator('.leaflet-marker-icon').count();
  console.log('Markers on map:', markers);

  const sidebarText = await page.locator('.px-3.py-2.text-xs').first().textContent().catch(() => 'N/A');
  console.log('Sidebar text:', sidebarText);

  console.log('\n=== Checking for map panes ===');
  const mapContainer = await page.locator('.leaflet-container').count();
  console.log('Map containers:', mapContainer);

  const tilePane = await page.locator('.leaflet-tile-pane').count();
  console.log('Tile panes:', tilePane);

  const markerPane = await page.locator('.leaflet-marker-pane').count();
  console.log('Marker panes:', markerPane);

  if (markers > 0) {
    console.log('\n=== Trying to click first marker ===');
    const markerBox = await page.locator('.leaflet-marker-icon').first().boundingBox();
    console.log('Marker position:', JSON.stringify(markerBox));
    
    await page.mouse.click(markerBox.x + 5, markerBox.y + 5);
    await page.waitForTimeout(2000);

    const modalAfterClick = await page.locator('.fixed.inset-0.z-50').count();
    console.log('Modal opened after click:', modalAfterClick > 0);

    const popupVisible = await page.locator('.leaflet-popup').count();
    console.log('Popup appeared:', popupVisible > 0);

    // Check pointer events on marker pane
    const markerPanePointerEvents = await page.evaluate(() => {
      const pane = document.querySelector('.leaflet-marker-pane');
      return pane ? window.getComputedStyle(pane).pointerEvents : 'not found';
    });
    console.log('Marker pane pointer events:', markerPanePointerEvents);
  } else {
    console.log('\nNo markers! Checking for API errors...');
    const apiResponse = await page.evaluate(async () => {
      const res = await fetch('/api/listings/map');
      const data = await res.json();
      return { status: res.status, listingCount: data.listings?.length };
    });
    console.log('API response:', JSON.stringify(apiResponse));
  }

  console.log('\n=== Console messages ===');
  consoleMessages.slice(-20).forEach(m => console.log(`[${m.type}] ${m.text.substring(0, 150)}`));

  await browser.close();
  console.log('\n=== DONE ===');
})().catch(e => { console.error('Test failed:', e.message); process.exit(1); });
