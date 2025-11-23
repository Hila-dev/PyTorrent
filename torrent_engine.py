import os
import json
from typing import Dict, List

import libtorrent as lt


class TorrentEngine:
    def __init__(self, download_path: str):
        self.download_path = download_path
        os.makedirs(self.download_path, exist_ok=True)
        self._session = lt.session()
        self._session.listen_on(6881, 6891)
        try:
            self._session.add_dht_router("router.utorrent.com", 6881)
            self._session.add_dht_router("router.bittorrent.com", 6881)
            self._session.add_dht_router("dht.transmissionbt.com", 6881)
            self._session.start_dht()
        except Exception:
            pass
        self._torrents: Dict[str, lt.torrent_handle] = {}
        self._meta: Dict[str, dict] = {}

        base_dir = os.path.dirname(os.path.abspath(__file__))
        state_dir = os.path.join(base_dir, ".pytorrent")
        os.makedirs(state_dir, exist_ok=True)
        self._state_path = os.path.join(state_dir, "state.json")
        self._legacy_state_path = os.path.join(self.download_path, ".pytorrent_state.json")

        self._load_state()

    def _save_state(self) -> None:

        try:
            data = {
                "torrents": [
                    {"id": tid, **meta}
                    for tid, meta in self._meta.items()
                ]
            }
            with open(self._state_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_state(self) -> None:
        data = None

        if os.path.exists(self._state_path):
            try:
                with open(self._state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = None

        if data is None and os.path.exists(self._legacy_state_path):
            try:
                with open(self._legacy_state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                with open(self._state_path, "w", encoding="utf-8") as f_new:
                    json.dump(data, f_new, ensure_ascii=False, indent=2)
                try:
                    os.remove(self._legacy_state_path)
                except Exception:
                    pass
            except Exception:
                data = None

        if not data:
            return

        torrents = data.get("torrents", [])
        for item in torrents:
            kind = item.get("kind")
            source = item.get("source")
            if not kind or not source:
                continue
            try:
                if kind == "file":
                    self.add_torrent_file(source)
                elif kind == "magnet":
                    self.add_magnet(source)
            except Exception:
                continue

    def _get_torrent_id(self, handle: lt.torrent_handle) -> str:
        try:
            info_hash = handle.info_hash()
            return str(info_hash)
        except Exception:
            return str(id(handle))

    def add_torrent_file(self, torrent_path: str, file_priorities: List[int] | None = None) -> str:
        info = lt.torrent_info(torrent_path)
        params = {
            "ti": info,
            "save_path": self.download_path,
        }
        if file_priorities is not None:
            params["file_priorities"] = file_priorities
        handle = self._session.add_torrent(params)
        tid = self._get_torrent_id(handle)
        self._torrents[tid] = handle
        self._meta[tid] = {
            "kind": "file",
            "source": torrent_path,
        }
        self._save_state()
        return tid

    def add_magnet(self, magnet_uri: str) -> str:
        params = {
            "url": magnet_uri,
            "save_path": self.download_path,
        }
        handle = self._session.add_torrent(params)
        tid = self._get_torrent_id(handle)
        self._torrents[tid] = handle
        self._meta[tid] = {
            "kind": "magnet",
            "source": magnet_uri,
        }
        self._save_state()
        return tid

    def inspect_torrent_file(self, torrent_path: str) -> dict:
        info = lt.torrent_info(torrent_path)
        files = info.files()
        file_list = []
        for idx in range(files.num_files()):
            file_list.append(
                {
                    "path": files.file_path(idx),
                    "size": files.file_size(idx),
                }
            )
        return {"name": info.name(), "files": file_list}

    def get_status_list(self) -> List[dict]:
        result: List[dict] = []
        to_remove: List[str] = []
        for tid, handle in list(self._torrents.items()):
            try:
                s = handle.status()
            except RuntimeError:
                to_remove.append(tid)
                continue
            state_names = [
                "Queued",
                "Checking",
                "Downloading metadata",
                "Downloading",
                "Finished",
                "Seeding",
                "Allocating",
                "Checking fastresume",
            ]
            if 0 <= s.state < len(state_names):
                state = state_names[s.state]
            else:
                state = "Unknown"
            downloaded = int(getattr(s, "total_done", 0))
            total_size = int(getattr(s, "total_wanted", 0))
            try:
                info_obj = handle.get_torrent_info()
                files = info_obj.files()
                try:
                    priorities = handle.file_priorities()
                except Exception:
                    priorities = []
                if priorities and len(priorities) == files.num_files():
                    size_sum = 0
                    for idx in range(files.num_files()):
                        if priorities[idx] > 0:
                            size_sum += files.file_size(idx)
                    if size_sum > 0:
                        total_size = size_sum
            except Exception:
                pass
            progress = float(getattr(s, "progress", 0.0))
            download_rate = float(getattr(s, "download_rate", 0.0))
            upload_rate = float(getattr(s, "upload_rate", 0.0))
            remaining = max(0, total_size - downloaded)
            if download_rate > 0 and remaining > 0:
                eta_sec = int(remaining / download_rate)
            else:
                eta_sec = -1
            name = getattr(s, "name", "")
            if not name:
                try:
                    info = handle.get_torrent_info()
                    name = info.name()
                except Exception:
                    name = ""
            is_paused = bool(getattr(s, "paused", False))
            is_seeding = bool(getattr(s, "is_seeding", False))
            display_state = state
            if is_paused:
                display_state = "Paused"
            elif is_seeding:
                display_state = "Seeding"
            else:
                if 0.0 < progress < 1.0 and download_rate < 50 * 1024:
                    display_state = "Resuming"
            num_peers = int(getattr(s, "num_peers", 0))
            result.append(
                {
                    "id": tid,
                    "name": name or "(metadata...)",
                    "progress": progress,
                    "download_rate": download_rate,
                    "upload_rate": upload_rate,
                    "state": display_state,
                    "total_size": total_size,
                    "downloaded": downloaded,
                    "num_peers": num_peers,
                    "eta": eta_sec,
                    "is_paused": is_paused,
                    "is_seeding": is_seeding,
                }
            )
        for tid in to_remove:
            self._torrents.pop(tid, None)
        return result

    def pause(self, torrent_id: str) -> None:
        handle = self._torrents.get(torrent_id)
        if handle is not None:
            try:
                handle.pause()
            except Exception:
                pass
        self._save_state()

    def resume(self, torrent_id: str) -> None:
        handle = self._torrents.get(torrent_id)
        if handle is not None:
            try:
                handle.resume()
            except Exception:
                pass

    def remove(self, torrent_id: str, delete_files: bool = False) -> None:
        handle = self._torrents.pop(torrent_id, None)
        self._meta.pop(torrent_id, None)
        if handle is None:
            return
        try:
            if delete_files and hasattr(lt, "options_t"):
                self._session.remove_torrent(handle, lt.options_t.delete_files)
            else:
                self._session.remove_torrent(handle)
        except Exception:
            try:
                self._session.remove_torrent(handle)
            except Exception:
                pass

    def close(self) -> None:
        for handle in list(self._torrents.values()):
            try:
                handle.pause()
            except Exception:
                pass
        self._torrents.clear()
        self._save_state()
