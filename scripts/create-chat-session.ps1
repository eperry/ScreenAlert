# Quick Chat Export Tool
# Usage: Save this as a snippet in VS Code or run directly

param(
    [string]$SessionName = "",
    [string]$Description = "Copilot chat session"
)

$RepoPath = "c:\Users\Ed\OneDrive\Documents\Development\ScreenAlert"
$ChatDir = "docs\copilot-chats"
$Date = Get-Date -Format "yyyy-MM-dd"

# Generate filename
if ($SessionName -eq "") {
    $SessionName = Read-Host "Enter session name (e.g., 'enhanced-detection')"
}

$FileName = "$Date`_$SessionName.md"
$FilePath = Join-Path $RepoPath (Join-Path $ChatDir $FileName)

# Create markdown template
$Template = @"
# Chat Session: $SessionName

**Date:** $Date
**Time:** $(Get-Date -Format "HH:mm:ss")  
**Duration:** [Add duration]
**Focus:** $Description

## Summary

[Brief overview of what was accomplished in this session]

## Key Implementation Details

### [Feature/Topic 1]

- [Implementation detail 1]
- [Implementation detail 2]
- [Implementation detail 3]

### [Feature/Topic 2]

- [Implementation detail 1]
- [Implementation detail 2]

## Files Modified

- `filename.py` - [description of changes]

## Configuration Changes

[Any new settings or configuration options added]

``````json
{
  "new_setting": "value"
}
``````

## Testing Results

- [Test result 1]
- [Test result 2]

## Next Steps

- [Follow-up task 1]
- [Follow-up task 2]

## Technical Notes

- [Important technical details]
- [Performance considerations]
- [Architecture decisions]

---

## Chat Content

[Paste your actual chat conversation here]

### User Query 1
[Your question or request]

### Assistant Response 1
[Copilot's response]

### User Query 2
[Your follow-up question]

### Assistant Response 2
[Copilot's response]

[Continue with the actual conversation...]
"@

# Write template to file
$Template | Out-File -FilePath $FilePath -Encoding UTF8

# Open in VS Code
if (Get-Command code -ErrorAction SilentlyContinue) {
    code $FilePath
} else {
    notepad $FilePath
}

Write-Host "Created chat session file: $FilePath"
Write-Host "Please fill in the chat content and save when complete."

# Offer to commit
$Commit = Read-Host "Commit to git when you're done? (y/n)"
if ($Commit -eq "y" -or $Commit -eq "Y") {
    Write-Host "Don't forget to run: git add $ChatDir && git commit -m `"Add chat session: $SessionName`""
}
