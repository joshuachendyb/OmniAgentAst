const puppeteer = require('puppeteer');
const path = require('path');

(async () => {
    console.log('Launching browser...');
    
    const browser = await puppeteer.launch({
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    
    console.log('Browser launched successfully');
    
    const page = await browser.newPage();
    
    // Set viewport to 800x600
    await page.setViewport({
        width: 800,
        height: 600,
        deviceScaleFactor: 1
    });
    
    // Load the HTML file
    const htmlPath = path.join(__dirname, 'Pencil_Digital_Sketch_Genesis.html');
    console.log('Loading HTML:', htmlPath);
    
    await page.goto('file://' + htmlPath, {
        waitUntil: 'networkidle0'
    });
    
    // Wait for canvas to be ready
    await page.waitForSelector('#canvas-wrapper canvas');
    
    // Wait for animation to complete (agents finish drawing)
    console.log('Waiting for animation to complete...');
    await new Promise(resolve => setTimeout(resolve, 5000));
    
    // Take screenshot of the canvas wrapper
    const canvasWrapper = await page.$('#canvas-wrapper');
    
    console.log('Taking screenshot...');
    await canvasWrapper.screenshot({
        path: 'Pencil_Cover_Puppeteer_800x600.png',
        type: 'png'
    });
    
    console.log('[OK] Screenshot saved: Pencil_Cover_Puppeteer_800x600.png');
    console.log('  Dimensions: 800x600');
    
    await browser.close();
    console.log('Browser closed');
})();
