# Create GitHub Release Script for ScreenAlert v1.2

# Release creation script - requires GitHub Personal Access Token
# Get your token from: https://github.com/settings/tokens

$releaseData = @{
    tag_name = "v1.2"
    target_commitish = "main"
    name = "ScreenAlert v1.2 - Enhanced UI and Automated Documentation"
    body = @"
## 🎉 Major Features

### Enhanced User Interface
- **Scrollable Settings Window**: Complete redesign using Canvas-based scrolling
- Mouse wheel support for smooth navigation
- Keyboard navigation (arrows, Page Up/Down, Home/End)
- Responsive scrolling that adapts to content size

### Automated Development Documentation
- **Git Hooks Integration**: Automatic chat export system
- Captures VS Code Copilot chat sessions on every commit
- Generates structured markdown documentation
- All exports included in the same commit
- **Session Management**: Auto-generated summaries and milestone markers

## 🔧 Technical Improvements

- Canvas-based scrollable interface in Tkinter
- Event-driven chat capture using pre-commit hooks
- Markdown documentation with structured templates
- Repository health monitoring and statistics

## 📊 What's New

- **40+ Chat Session Exports**: Complete development history preserved
- **Documentation System**: Comprehensive session summaries and milestone tracking
- **Git Integration**: Pre-commit and post-commit hooks for automatic documentation
- **UI Enhancement**: Scrollable settings window supporting unlimited content

## 🚀 Installation

1. Download the source code from this release
2. Extract to your desired location
3. Run ``python screenalert.py`` to start the application
4. The git hooks will automatically install on first commit

## 📖 Documentation

- [Complete Release Notes](https://github.com/eperry/ScreenAlert/blob/main/RELEASE_NOTES_v1.2.md)
- [Chat Export System Guide](https://github.com/eperry/ScreenAlert/tree/main/docs/copilot-chats)

---

**Full Changelog**: https://github.com/eperry/ScreenAlert/compare/v1.0...v1.2
"@
    draft = $false
    prerelease = $false
}

$jsonData = $releaseData | ConvertTo-Json -Depth 10

Write-Host "=== GitHub Release Creation Script ==="
Write-Host ""
Write-Host "To create the release, you need a GitHub Personal Access Token."
Write-Host ""
Write-Host "Steps:"
Write-Host "1. Go to: https://github.com/settings/tokens"
Write-Host "2. Click 'Generate new token (classic)'"
Write-Host "3. Give it a name like 'ScreenAlert Release'"
Write-Host "4. Select scopes: 'repo' (Full control of private repositories)"
Write-Host "5. Copy the generated token"
Write-Host ""
Write-Host "Then run this command (replace YOUR_TOKEN with your actual token):"
Write-Host ""
Write-Host "```powershell"
Write-Host "`$token = 'YOUR_GITHUB_TOKEN_HERE'"
Write-Host "`$headers = @{"
Write-Host "    'Authorization' = `"token `$token`""
Write-Host "    'Accept' = 'application/vnd.github.v3+json'"
Write-Host "    'Content-Type' = 'application/json'"
Write-Host "}"
Write-Host ""
Write-Host "`$response = Invoke-RestMethod -Uri 'https://api.github.com/repos/eperry/ScreenAlert/releases' -Method Post -Headers `$headers -Body @'"
Write-Host $jsonData
Write-Host "'@"
Write-Host ""
Write-Host "Write-Host 'Release created successfully!'"
Write-Host "Write-Host `"Release URL: `$(`$response.html_url)`""
Write-Host "```"
Write-Host ""
Write-Host "=== OR USE THE WEB INTERFACE ==="
Write-Host ""
Write-Host "Easier option: Use the GitHub web interface that should be open in your browser"
Write-Host "Just copy and paste the release notes from above into the description field."
