![My Image](https://github.com/Hila-dev/PyTorrent/blob/ac544ad9c699abdd5552b3d927df3d11da10fd57/Screenshot%202025-11-23%20043544.png)

# PyTorrent

PyTorrent is a minimal desktop BitTorrent client written in Python using **PySide6** for the GUI and **libtorrent** for the torrent backend. It supports both `.torrent` files and magnet links and provides a simple, modern interface.

## Features

- Add downloads from **.torrent files**
- Add downloads from **magnet links**
- Show progress, speeds, peers, ETA and status
- Configurable download folder (default: system `Downloads`)
- System tray integration (minimize to tray, restore, quit)
- Dark, modern custom QSS theme

## Requirements

- Python 3.10 or 3.11 (recommended)
- `PySide6`
- `libtorrent`
- On Windows, you may need the extra `libtorrent-windows-dll` package

All Python dependencies used by this project are listed in `requirements.txt`.

## Installation

1. Clone this repository or download the project files.
2. (Optional) Create and activate a virtual environment.
3. Install Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```

### Notes about libtorrent on Windows

- The `libtorrent` wheel availability depends on your Python version and architecture.
- If `pip install libtorrent` fails, check the **Files** section on PyPI: https://pypi.org/project/libtorrent/
- Make sure your Python version is supported, or install a compatible version of Python.

## Running the application

From the project root (where `main.py` is located):

```bash
python main.py
```

When the app starts:

1. Use **Magnet** input and `Add magnet` button to start a download from a magnet link.
2. Use **Add .torrent** to load a `.torrent` file from disk.
3. Use **Pause / Resume**, **Delete**, and **Open folder** buttons to control downloads.
4. Use the system tray icon to hide the window, restore it, or quit the application.

## State and configuration

- Download path defaults to your home `Downloads` directory, but can be changed in the UI.
- Torrents and their metadata are persisted in the `.pytorrent/state.json` file next to the application, so active torrents are restored on restart.


