# Debug script to help diagnose the issue with index.html
Write-Host "Debugging Photo Heatmap Viewer Application" -ForegroundColor Green

# Create a simple wrapper to test both HTML files with the same JSON data
$debugHtml = @"
<!DOCTYPE html>
<html>
<head>
    <title>Debug JSON Loading</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .result { margin-top: 10px; padding: 10px; border: 1px solid #ccc; }
        .error { color: red; }
        .success { color: green; }
        pre { background: #f5f5f5; padding: 10px; overflow: auto; max-height: 300px; }
    </style>
</head>
<body>
    <h1>JSON Loading Debug Test</h1>
    
    <div>
        <h2>Test Fetch API</h2>
        <button id="testFetch">Test Fetch JSON</button>
        <div id="fetchResult" class="result"></div>
    </div>
    
    <script>
        // Debug logging
        function log(message, isError = false) {
            console.log(message);
            const logElem = document.getElementById('fetchResult');
            logElem.innerHTML += `<div class="\${isError ? 'error' : 'success'}">\${message}</div>`;
        }

        // Test button
        document.getElementById('testFetch').addEventListener('click', function() {
            log('Fetching from /api/markers...');
            
            fetch('/api/markers')
                .then(response => {
                    log(`Response status: \${response.status}`);
                    if (!response.ok) {
                        throw new Error(`HTTP error! Status: \${response.status}`);
                    }
                    return response.text(); // Get as text first to inspect
                })
                .then(text => {
                    try {
                        log(`Raw response length: \${text.length} chars`);
                        
                        // Log the first and last few characters to check for issues
                        log(`First 50 chars: \${text.substring(0, 50)}`);
                        log(`Last 50 chars: \${text.substring(text.length - 50)}`);
                        
                        // Try to parse as JSON
                        const data = JSON.parse(text);
                        
                        // Check data structure
                        if (Array.isArray(data)) {
                            log(`Successfully parsed as array with \${data.length} items`);
                        } else if (typeof data === 'object') {
                            log(`Successfully parsed as object with keys: \${Object.keys(data).join(', ')}`);
                            
                            // Check for photos and libraries
                            if (Array.isArray(data.photos)) {
                                log(`Found \${data.photos.length} photos`);
                            } else {
                                log('No photos array found', true);
                            }
                            
                            if (Array.isArray(data.libraries)) {
                                log(`Found \${data.libraries.length} libraries`);
                            } else {
                                log('No libraries array found', true);
                            }
                        } else {
                            log(`Unexpected data type: \${typeof data}`, true);
                        }
                    } catch (parseError) {
                        log(`JSON parse error: \${parseError.message}`, true);
                        
                        // Try to identify where the parsing error occurred
                        const errorMatch = parseError.message.match(/position (\d+)/);
                        if (errorMatch && errorMatch[1]) {
                            const pos = parseInt(errorMatch[1]);
                            log(`Error near position \${pos}`);
                            log(`Content around error: \${text.substring(Math.max(0, pos - 20), pos)}|\${text.substring(pos, pos + 20)}`);
                        }
                    }
                })
                .catch(error => {
                    log(`Fetch error: \${error.message}`, true);
                });
        });
    </script>
</body>
</html>
"@

# Write the debug HTML file
$debugHtmlPath = Join-Path (Get-Location) "debug.html"
$debugHtml | Out-File -Encoding utf8 $debugHtmlPath

# Copy the debug.html to the photos_heatmap_viewer folder
$targetPath = Join-Path (Get-Location) "photos_heatmap_viewer\debug.html"
Copy-Item -Path $debugHtmlPath -Destination $targetPath -Force

Write-Host "Debug files created:"
Write-Host "- $debugHtmlPath (main debug tool)" -ForegroundColor Cyan
Write-Host "- $targetPath (copy for server access)" -ForegroundColor Cyan
Write-Host ""
Write-Host "To debug the issue:" -ForegroundColor Yellow
Write-Host "1. Start your server" -ForegroundColor Yellow
Write-Host "2. Open http://localhost:YOUR_PORT/debug.html in your browser" -ForegroundColor Yellow
Write-Host "3. Click 'Test Fetch JSON' to examine the JSON response" -ForegroundColor Yellow
Write-Host ""
Write-Host "This will help identify if there are issues with the JSON data or the frontend parsing."
