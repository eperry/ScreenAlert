# Git Hooks Setup Script for Copilot Chat Auto-Export
# This script sets up git hooks to automatically export chat sessions during commits

param(
    [switch]$Remove,
    [switch]$Test
)

$RepoRoot = "c:\Users\Ed\OneDrive\Documents\Development\ScreenAlert"
$HooksDir = Join-Path $RepoRoot ".git\hooks"
$ChatDir = Join-Path $RepoRoot "docs\copilot-chats"

function Write-Status {
    param([string]$Message, [string]$Type = "Info")
    $color = switch ($Type) {
        "Success" { "Green" }
        "Warning" { "Yellow" }
        "Error" { "Red" }
        default { "White" }
    }
    Write-Host "[$Type] $Message" -ForegroundColor $color
}

function Test-GitHooks {
    Write-Status "Testing git hooks configuration..." "Info"
    
    # Test if hooks exist
    $preCommitPath = Join-Path $HooksDir "pre-commit"
    $postCommitPath = Join-Path $HooksDir "post-commit"
    
    if (Test-Path $preCommitPath) {
        Write-Status "✓ Pre-commit hook exists" "Success"
    } else {
        Write-Status "✗ Pre-commit hook not found" "Error"
    }
    
    if (Test-Path $postCommitPath) {
        Write-Status "✓ Post-commit hook exists" "Success"
    } else {
        Write-Status "✗ Post-commit hook not found" "Error"
    }
    
    # Test if chat directory exists
    if (Test-Path $ChatDir) {
        Write-Status "✓ Chat directory exists: $ChatDir" "Success"
    } else {
        Write-Status "✗ Chat directory not found: $ChatDir" "Error"
    }
    
    # Test if we're in a git repository
    try {
        git status | Out-Null
        Write-Status "✓ Git repository detected" "Success"
    }
    catch {
        Write-Status "✗ Not a git repository or git not available" "Error"
    }
    
    # Check for required tools
    $requiredTools = @("git", "bash")
    foreach ($tool in $requiredTools) {
        if (Get-Command $tool -ErrorAction SilentlyContinue) {
            Write-Status "✓ $tool is available" "Success"
        } else {
            Write-Status "✗ $tool is not available in PATH" "Error"
        }
    }
}

function Install-GitHooks {
    Write-Status "Installing git hooks for Copilot chat auto-export..." "Info"
    
    # Ensure hooks directory exists
    if (-not (Test-Path $HooksDir)) {
        New-Item -ItemType Directory -Path $HooksDir -Force | Out-Null
        Write-Status "Created hooks directory: $HooksDir" "Success"
    }
    
    # Ensure chat directory exists
    if (-not (Test-Path $ChatDir)) {
        New-Item -ItemType Directory -Path $ChatDir -Force | Out-Null
        Write-Status "Created chat directory: $ChatDir" "Success"
    }
    
    # Check if hooks exist
    $preCommitPath = Join-Path $HooksDir "pre-commit"
    $postCommitPath = Join-Path $HooksDir "post-commit"
    
    if (Test-Path $preCommitPath) {
        Write-Status "✓ Pre-commit hook installed" "Success"
    } else {
        Write-Status "✗ Pre-commit hook not found - may need to be recreated" "Error"
    }
    
    if (Test-Path $postCommitPath) {
        Write-Status "✓ Post-commit hook installed" "Success"
    } else {
        Write-Status "✗ Post-commit hook not found - may need to be recreated" "Error"
    }
    
    Write-Status "Git hooks setup complete!" "Success"
    Write-Status "From now on, every commit will automatically export Copilot chat sessions." "Info"
}

function Remove-GitHooks {
    Write-Status "Removing git hooks..." "Warning"
    
    $preCommitPath = Join-Path $HooksDir "pre-commit"
    $postCommitPath = Join-Path $HooksDir "post-commit"
    
    if (Test-Path $preCommitPath) {
        Remove-Item $preCommitPath -Force
        Write-Status "Removed pre-commit hook" "Success"
    }
    
    if (Test-Path $postCommitPath) {
        Remove-Item $postCommitPath -Force
        Write-Status "Removed post-commit hook" "Success"
    }
    
    Write-Status "Git hooks removed. Chat auto-export is now disabled." "Warning"
}

function Show-Usage {
    Write-Host @"
Git Hooks Setup for Copilot Chat Auto-Export

This script manages git hooks that automatically export Copilot chat sessions
during the commit process.

USAGE:
    .\setup-git-hooks.ps1           # Install/setup hooks
    .\setup-git-hooks.ps1 -Test     # Test current hook installation
    .\setup-git-hooks.ps1 -Remove   # Remove/disable hooks

FEATURES:
    • Pre-commit hook: Captures current chat state before each commit
    • Post-commit hook: Updates session summaries and creates milestones
    • Automatic staging: Chat exports are added to the current commit
    • Smart filtering: Only captures recent chat data (last 24 hours)
    • Milestone markers: Creates special documentation at commit intervals

REQUIREMENTS:
    • Git for Windows (with bash support)
    • PowerShell 5.1 or later
    • VS Code with GitHub Copilot extension

DIRECTORIES:
    • Hooks: .git\hooks\
    • Chat exports: docs\copilot-chats\
    • Logs: docs\copilot-chats\git-hook-export.log

For more information, see: scripts\README.md
"@
}

# Main execution
Set-Location $RepoRoot

if ($Remove) {
    Remove-GitHooks
} elseif ($Test) {
    Test-GitHooks
} elseif ($args.Count -eq 0) {
    Install-GitHooks
    Write-Status "`nTesting installation..." "Info"
    Test-GitHooks
} else {
    Show-Usage
}

Write-Host "`nNext steps:" -ForegroundColor Cyan
Write-Host "1. Make a test commit to verify the hooks work" -ForegroundColor Gray
Write-Host "2. Check docs/copilot-chats/ for the exported session" -ForegroundColor Gray
Write-Host "3. Review the git-hook-export.log for any issues" -ForegroundColor Gray
