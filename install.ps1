# AI Learning Agent — One-Command Installer
# Usage: .\install.ps1 -VaultPath "C:\Users\YourName\MyVault"
# Run from the monorepo root directory.

param(
    [Parameter(Mandatory = $true)]
    [string]$VaultPath
)

$ErrorActionPreference = "Stop"

$pluginDir = Join-Path $VaultPath ".obsidian\plugins\ai-learning-agent"
$backendDir = Join-Path $pluginDir "backend"
$backendSrcDir = Join-Path $backendDir "src"

Write-Host "=== AI Learning Agent Installer ===" -ForegroundColor Cyan
Write-Host ""

# 1. Build Obsidian plugin
Write-Host "[1/4] Building Obsidian plugin..." -ForegroundColor Yellow
pnpm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed. Check the errors above." -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Plugin built" -ForegroundColor Green

# 2. Create plugin directory in Obsidian
Write-Host "[2/4] Installing plugin to: $pluginDir" -ForegroundColor Yellow
New-Item -ItemType Directory -Path $pluginDir -Force | Out-Null
Copy-Item -Path "apps\obsidian-plugin\main.js" -Destination $pluginDir -Force
Copy-Item -Path "apps\obsidian-plugin\manifest.json" -Destination $pluginDir -Force
Copy-Item -Path "apps\obsidian-plugin\styles.css" -Destination $pluginDir -Force
Write-Host "  ✓ Plugin files copied" -ForegroundColor Green

# 3. Copy Python backend
Write-Host "[3/4] Copying Python backend..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $backendSrcDir -Force | Out-Null
Copy-Item -Path "python\backend\src\app" -Destination $backendSrcDir -Recurse -Force
Copy-Item -Path "python\backend\pyproject.toml" -Destination $backendDir -Force
Copy-Item -Path "python\backend\uv.lock" -Destination $backendDir -Force
Copy-Item -Path "python\backend\.python-version" -Destination $backendDir -Force
Write-Host "  ✓ Python backend copied" -ForegroundColor Green

# 4. Install Python dependencies
Write-Host "[4/4] Installing Python dependencies (uv sync)..." -ForegroundColor Yellow
Push-Location $backendDir
try {
    uv sync
    Write-Host "  ✓ Python dependencies installed" -ForegroundColor Green
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "=== Installation Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Restart Obsidian (or reload plugins: Ctrl+P → 'Reload app')" -ForegroundColor White
Write-Host "  2. Go to Settings → AI Learning Agent" -ForegroundColor White
Write-Host "  3. Set your API key (DeepSeek/OpenAI/Ollama)" -ForegroundColor White
Write-Host "  4. Set your Vault Path" -ForegroundColor White
Write-Host "  5. The plugin will auto-start the backend" -ForegroundColor White
Write-Host "  6. Use Ctrl+Shift+L to open the AI chat panel" -ForegroundColor White
Write-Host ""
Write-Host "For RAG search (search your notes):" -ForegroundColor White
Write-Host "  - Enable RAG_ENABLED=true in the backend .env" -ForegroundColor White
Write-Host "  - Wait for BGE-M3 model to download (~2GB, first time only)" -ForegroundColor White
Write-Host "  - Index your vault: POST /api/vault/index" -ForegroundColor White
