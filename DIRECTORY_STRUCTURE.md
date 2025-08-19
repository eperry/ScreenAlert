# ScreenAlert Directory Structure

## Root Level (Core Application)
- `screenalert.py` - Main application file
- `screenalert_config.json` - Configuration file
- `screenalert_requirements.txt` - Python dependencies
- `README.md` - Main documentation
- `SECURITY.md` - Security policy

## Organized Directories

### `/build/` - Build System & Packaging
- Build scripts for various systems (Nuitka, auto-py-to-exe, etc.)
- Installer creation scripts (MSI, portable)
- Build configuration and optimization files
- Build cache analysis tools

### `/docs/` - Documentation
- Comprehensive guides (antivirus, code signing, release creation)
- Technical documentation (logging, optimization, alternatives)
- Release notes and verification documents
- Development and testing documentation

### `/scripts/` - Utility Scripts
- Application launchers and shortcuts
- Installation and portable creation scripts
- Release and deployment utilities

### `/security/` - Security Components
- Code signing scripts and tools
- Certificate management utilities
- `/certificates/` - Certificate files (PFX, CER)

### `/tests/` - Test Suite
- Unit tests for core functionality
- Compatibility tests
- Testing utilities

### `/ScreenEvents/` - Application Data
- Screenshot storage for alerts
- Runtime generated content

### `.github/` - GitHub Integration
- Workflow configurations
- CI/CD automation

## Development Environment
- `.venv/` - Python virtual environment
- `.vscode/` - VS Code settings
- `.gitignore` - Git ignore patterns
- `.git/` - Git repository data

## Benefits of New Structure
1. **Professional Organization** - Clear separation of concerns
2. **Easy Navigation** - Related files grouped together
3. **Build Isolation** - All build tools in dedicated directory
4. **Security Focus** - Dedicated security directory with certificates
5. **Documentation Central** - All docs in one accessible location
6. **Clean Root** - Only essential files at root level
7. **Development Ready** - Proper test and script organization

## Usage Notes
- Build scripts now located in `/build/` directory
- Documentation consolidated in `/docs/` for easy reference
- Security certificates safely organized in `/security/certificates/`
- Test files properly structured in `/tests/` directory
- Utility scripts grouped in `/scripts/` for automation
