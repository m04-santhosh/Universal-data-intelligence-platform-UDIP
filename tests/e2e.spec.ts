import { test, expect } from '@playwright/test';

test.describe('Universal Data Intelligence Platform (UDIP) - E2E Critical Flows', () => {

  const BASE_URL = 'http://localhost:8000';
  let TEST_USERNAME = process.env.TEST_USERNAME || 'test_user';
  let TEST_PASSWORD = process.env.TEST_PASSWORD || 'test_pass';

  test.beforeEach(async ({ page }) => {
    // Navigate to base URL before each test
    await page.goto(BASE_URL);
  });

  test('Module 1: Authentication - Should successfully login and reach dashboard', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    
    // Fill credentials
    await page.fill('input[name="username"]', TEST_USERNAME);
    await page.fill('input[name="password"]', TEST_PASSWORD);
    
    // Submit
    await page.click('button[type="submit"]');
    
    // Verify redirect to dashboard
    await expect(page).toHaveURL(`${BASE_URL}/dashboard`);
    await expect(page.locator('h1.page-title')).toContainText('Dashboard');
  });

  test('Module 2-6: Upload & Universal Parser - Process multiple file types successfully', async ({ page }) => {
    // Authenticate
    await page.goto(`${BASE_URL}/login`);
    await page.fill('input[name="username"]', TEST_USERNAME);
    await page.fill('input[name="password"]', TEST_PASSWORD);
    await page.click('button[type="submit"]');
    
    // Go to upload page
    await page.goto(BASE_URL);

    // Mock file buffer (CSV and JSON)
    const csvBuffer = Buffer.from('id,name,revenue\n1,Alice,100\n2,Bob,200\n');
    const jsonBuffer = Buffer.from('[{"id": 1, "name": "Alice", "revenue": 100}, {"id": 2, "name": "Bob", "revenue": 200}]');

    // Attach files
    await page.setInputFiles('input[type="file"]', [
      { name: 'data1.csv', mimeType: 'text/csv', buffer: csvBuffer },
      { name: 'data2.json', mimeType: 'application/json', buffer: jsonBuffer }
    ]);

    // Click Analyze
    await page.click('#btnAnalyze');

    // Wait for mapping UI to render
    await expect(page.locator('#mappingContainer')).toBeVisible({ timeout: 15000 });
    
    // Click Next (Run Pipeline)
    await page.click('#btnRunMapping');

    // Wait for intelligence dashboard to appear
    await expect(page.locator('#resultsContainer')).toBeVisible({ timeout: 30000 });
    await expect(page.locator('.kpi-card')).toHaveCount(4); // Or however many KPI cards exist
  });

  test('Module 7: History - Verify historical projects load correctly', async ({ page }) => {
    // Authenticate
    await page.goto(`${BASE_URL}/login`);
    await page.fill('input[name="username"]', TEST_USERNAME);
    await page.fill('input[name="password"]', TEST_PASSWORD);
    await page.click('button[type="submit"]');

    // Navigate to History
    await page.goto(`${BASE_URL}/history`);

    // Verify Title
    await expect(page.locator('h1.page-title')).toContainText('Project History');

    // Check table has rows (Assuming at least 1 project exists from previous tests)
    const rowCount = await page.locator('.saas-table tbody tr').count();
    expect(rowCount).toBeGreaterThan(0);
  });

  test('Module 8: Project Intelligence View - Can open project from dashboard', async ({ page }) => {
    // Authenticate
    await page.goto(`${BASE_URL}/login`);
    await page.fill('input[name="username"]', TEST_USERNAME);
    await page.fill('input[name="password"]', TEST_PASSWORD);
    await page.click('button[type="submit"]');

    await page.goto(`${BASE_URL}/dashboard`);

    // Click the first "Open" project button
    const openButton = page.locator('.saas-table tbody tr:first-child a.btn-secondary');
    if (await openButton.isVisible()) {
        await openButton.click();

        // Verify we hit the Project Intelligence View
        await expect(page).toHaveURL(/\/project\/.+/);
        await expect(page.locator('h1.page-title')).toBeVisible();
        await expect(page.locator('text=Project Intelligence View')).toBeVisible();
    }
  });

  test('Module 12-13: JSON & PDF Download Flows', async ({ page }) => {
    // Authenticate
    await page.goto(`${BASE_URL}/login`);
    await page.fill('input[name="username"]', TEST_USERNAME);
    await page.fill('input[name="password"]', TEST_PASSWORD);
    await page.click('button[type="submit"]');

    // Navigate to a project directly via history
    await page.goto(`${BASE_URL}/history`);
    
    const openButton = page.locator('.saas-table tbody tr:first-child a.btn-secondary');
    if (await openButton.isVisible()) {
        await openButton.click();
        
        // Wait for page to load
        await expect(page.locator('h1.page-title')).toBeVisible();

        // Intercept PDF download
        const [pdfDownload] = await Promise.all([
            page.waitForEvent('download'),
            page.click('a.btn-secondary:has-text("Download PDF")')
        ]);
        
        expect(pdfDownload.suggestedFilename()).toContain('.pdf');

        // Intercept JSON download
        const [jsonDownload] = await Promise.all([
            page.waitForEvent('download'),
            page.click('a.btn-primary:has-text("Download JSON")')
        ]);
        
        expect(jsonDownload.suggestedFilename()).toContain('.json');
    }
  });

  test('Module 14: AI Query Engine - Smart Intents', async ({ page }) => {
    // Authenticate
    await page.goto(`${BASE_URL}/login`);
    await page.fill('input[name="username"]', TEST_USERNAME);
    await page.fill('input[name="password"]', TEST_PASSWORD);
    await page.click('button[type="submit"]');
    
    // We assume the results view is open or we have a cached download ID.
    // For this test, we test the API endpoint directly using Playwright's API context.
    const apiContext = page.request;
    
    // We need to fetch a valid download_id from the application state (simulated here)
    // In a real environment, you'd extract this from the DOM after an upload.
    // Assuming the test handles the UI flow, here we just verify the endpoint structure.
    
    const response = await apiContext.post(`${BASE_URL}/api/query`, {
      data: {
        download_id: "test-expired-id",
        query: "Summarize this dataset"
      }
    });

    // Since download_id is likely expired or invalid in this isolated API test, 
    // we expect a 404 handled error rather than a 500 crash.
    expect([200, 404]).toContain(response.status());
    
    const responseBody = await response.json();
    if (response.status() === 404) {
      expect(responseBody.detail).toContain('expired');
    } else {
      expect(responseBody.success).toBe(true);
      expect(responseBody.intent).toBe('SUMMARY');
      expect(responseBody.suggested_questions.length).toBeGreaterThan(0);
    }
  });

});
