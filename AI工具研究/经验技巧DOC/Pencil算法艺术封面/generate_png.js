const puppeteer = require('puppeteer');
const path = require('path');

(async () => {
    console.log('Launching browser...');
    
    const browser = await puppeteer.launch({
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    
    const page = await browser.newPage();
    
    // Set viewport to 800x600
    await page.setViewport({
        width: 800,
        height: 600,
        deviceScaleFactor: 2 // High DPI for sharp image
    });
    
    // Load the HTML file
    const htmlPath = path.resolve(__dirname, 'Pencil_Digital_Sketch_Genesis.html');
    console.log('Loading HTML:', htmlPath);
    
    await page.goto('file://' + htmlPath, {
        waitUntil: 'networkidle0'
    });
    
    // Wait for canvas to be created and drawing to complete
    console.log('Waiting for generative art to complete...');
    await page.waitForTimeout(5000); // Wait 5 seconds for drawing to complete
    
    // Find and screenshot the canvas
    const canvas = await page.$('canvas');
    if (canvas) {
        await canvas.screenshot({
            path: 'Pencil_Algorithmic_Cover.png',
            type: 'png'
        });
        console.log('✓ PNG saved: Pencil_Algorithmic_Cover.png');
    } else {
        console.error('Canvas not found!');
    }
    
    await browser.close();
    console.log('Done!');
})();
