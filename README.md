# ScreenAlert - Screen Monitoring and Alert System

**Status**: Beta Testing - Now with Antivirus-Safe Executables!

## 📖 Overview

ScreenAlert is a sophisticated tool for monitoring applications where you need to watch multiple screen areas for changes. Perfect for monitoring systems, websites, dashboards, and any visual interface that requires constant observation.

**Key Features**:
- Multi-region screen monitoring
- Real-time change detection
- Event logging and screenshots
- Alert notifications
- Window-specific targeting

## 🔒 Antivirus-Safe Distribution

**PyInstaller has been replaced** due to persistent false positive detections. ScreenAlert now uses modern, antivirus-friendly build tools:

### 🏆 Nuitka (Recommended)
- **Single executable**: `dist-nuitka/ScreenAlert.exe` (78MB)
- **Native compilation**: C++ compiled for best AV compatibility
- **Zero false positives**: Tested with Windows Defender and major AV suites

### 🔧 cx_Freeze (Development)
- **Directory distribution**: `dist-cxfreeze/` (314MB)
- **Fast builds**: Quick iteration for development
- **Reliable**: Standard Python runtime, no compression triggers

## 🚀 Quick Start

### Download & Run
1. Download latest release from GitHub
2. Extract and run `ScreenAlert.exe`
3. No installation required!

### Build from Source
```bash
git clone https://github.com/your-repo/ScreenAlert
cd ScreenAlert
pip install -r screenalert_requirements.txt

# Build with Nuitka (recommended)
python build_nuitka.py

# Or build with cx_Freeze
python setup_cx_freeze.py
```

## 🖥️ Usage

### Window Selection
<img width="705" height="626" alt="image" src="https://github.com/user-attachments/assets/0a47a391-0581-4282-98c7-a1fad2cd80d2" />

### Main Monitoring Interface
<img width="1189" height="370" alt="image" src="https://github.com/user-attachments/assets/d7116df0-57d6-4ed6-b95f-e820fd54b380" />

## 🛡️ Security & Compliance

- **Observation Only**: Tool performs no automation or interaction
- **Privacy Focused**: All data stays on your local machine
- **Logging**: Comprehensive event tracking for compliance
- **Best Practices**: Follows application security guidelines

## 📁 Project Structure

```
ScreenAlert/
├── screenalert.py              # Main application
├── screenalert_config.json     # Configuration
├── build_nuitka.py            # Production build script
├── setup_cx_freeze.py         # Development build script
├── dist-nuitka/               # Production executable
├── dist-cxfreeze/             # Development distribution
└── ScreenEvents/              # Screenshot storage
```

## 🔧 Dependencies

- Python 3.11+
- OpenCV (cv2)
- scikit-image
- tkinter (included with Python)
- PyWin32 (Windows-specific)

## 📋 Configuration

Edit `screenalert_config.json` to customize:
- Monitoring regions
- Alert thresholds
- Screenshot settings
- Notification preferences

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with both build methods
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

Having issues? 
- Check the antivirus troubleshooting guide
- Review the build comparison report
- Open an issue on GitHub

---

**Note**: If you're upgrading from a PyInstaller version, please download the new Nuitka-built executable for the best antivirus compatibility.
