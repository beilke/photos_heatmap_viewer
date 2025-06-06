# Debug API response PowerShell script
# This script will make a request to the API endpoint and show us the raw response

Write-Host "Checking API response format..." -ForegroundColor Cyan
Write-Host "Making a request to /api/markers endpoint..." -ForegroundColor Yellow

# Create a temporary HTML file to check the API response
$debugHtmlContent = @"
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Debug Tool</title>
    <style>
        body { font-family: monospace; margin: 20px; }
        #responseContainer { white-space: pre-wrap; word-break: break-word; border: 1px solid #ccc; padding: 10px; max-height: 500px; overflow: auto; }
        .controls { margin-bottom: 10px; }
        button { padding: 5px 10px; }
    </style>
</head>
<body>
    <h1>API Debug Tool</h1>
    <div class="controls">
        <button id="fetchBtn">Fetch API Data</button>
        <button id="validateBtn">Validate JSON</button>
        <span id="statusMessage"></span>
    </div>
    <h3>Raw Response:</h3>
    <div id="responseContainer">Click "Fetch API Data" to see raw response</div>
    
    <h3>Response Headers:</h3>
    <div id="headersContainer"></div>

    <script>
        const fetchBtn = document.getElementById('fetchBtn');
        const validateBtn = document.getElementById('validateBtn');
        const responseContainer = document.getElementById('responseContainer');
        const headersContainer = document.getElementById('headersContainer');
        const statusMessage = document.getElementById('statusMessage');
        
        let rawResponse = '';

        fetchBtn.addEventListener('click', async () => {
            statusMessage.textContent = 'Fetching...';
            try {
                // Use fetch but don't parse as JSON yet
                const response = await fetch('/api/markers');
                
                // Display headers
                headersContainer.innerHTML = '';
                const headersList = document.createElement('ul');
                for (const [key, value] of response.headers.entries()) {
                    const headerItem = document.createElement('li');
                    headerItem.textContent = `${key}: ${value}`;
                    headersList.appendChild(headerItem);
                }
                headersContainer.appendChild(headersList);
                
                // Get raw text
                rawResponse = await response.text();
                
                // Display raw response
                responseContainer.textContent = rawResponse;
                
                statusMessage.textContent = `Fetched ${rawResponse.length} characters`;
            } catch (error) {
                responseContainer.textContent = `Error: ${error.message}`;
                statusMessage.textContent = 'Error!';
            }
        });
        
        validateBtn.addEventListener('click', () => {
            if (!rawResponse) {
                statusMessage.textContent = 'Fetch data first!';
                return;
            }
            
            try {
                // Try to parse as JSON
                const parsed = JSON.parse(rawResponse);
                statusMessage.textContent = 'Valid JSON!';
                
                // Show some info about the structure
                let structureInfo = '';
                if (Array.isArray(parsed)) {
                    structureInfo = `Array with ${parsed.length} items`;
                    if (parsed.length > 0) {
                        structureInfo += `\nFirst item keys: ${Object.keys(parsed[0]).join(', ')}`;
                    }
                } else {
                    structureInfo = `Object with keys: ${Object.keys(parsed).join(', ')}`;
                    if (parsed.photos) {
                        structureInfo += `\nphotos: Array with ${parsed.photos.length} items`;
                    }
                    if (parsed.libraries) {
                        structureInfo += `\nlibraries: Array with ${parsed.libraries.length} items`;
                    }
                }
                
                responseContainer.textContent = structureInfo;
            } catch (error) {
                statusMessage.textContent = 'Invalid JSON!';
                
                // Find the position of the error
                const match = error.message.match(/position (\d+)/);
                if (match && match[1]) {
                    const pos = parseInt(match[1]);
                    const start = Math.max(0, pos - 20);
                    const end = Math.min(rawResponse.length, pos + 20);
                    const excerpt = rawResponse.substring(start, end);
                    responseContainer.textContent = `Error at position ${pos}: ${error.message}\n\nNear: "${excerpt}"`;
                } else {
                    responseContainer.textContent = `Error: ${error.message}`;
                }
            }
        });
    </script>
</body>
</html>
"@

Set-Content -Path "debug_api.html" -Value $debugHtmlContent

Write-Host "`nCreated debug_api.html" -ForegroundColor Green
Write-Host "Please open http://localhost:8000/debug_api.html in your browser" -ForegroundColor Yellow
Write-Host "Click 'Fetch API Data' to see the raw response and check for any issues" -ForegroundColor Yellow
