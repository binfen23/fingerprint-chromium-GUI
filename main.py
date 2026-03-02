# app.py
import webview
import json
import os
import subprocess
import uuid
import random
import time
import threading
import ctypes
import sys

# 最小化控制台窗口
if sys.platform == 'win32':
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 6)

PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles_config.json")
CHROME_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fingerprint-chromium", "chrome.exe")

os.makedirs(PROFILES_DIR, exist_ok=True)


def load_profiles():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_profiles(profiles):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)


# WebGL 渲染器和供应商的合理组合
WEBGL_CONFIGS = [
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4080 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4090 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1080 Ti Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, AMD Radeon RX 6700 XT Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, AMD Radeon RX 6800 XT Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, AMD Radeon RX 7900 XTX Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) UHD Graphics 770 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)"},
]

TIMEZONES = [
    "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
    "America/Anchorage", "Pacific/Honolulu", "America/Toronto", "America/Vancouver",
    "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Moscow",
    "Asia/Tokyo", "Asia/Shanghai", "Asia/Seoul", "Asia/Singapore",
    "Asia/Dubai", "Asia/Kolkata", "Australia/Sydney", "Pacific/Auckland"
]

LANGUAGES = [
    "en-US", "en-GB", "zh-CN", "zh-TW", "ja-JP", "ko-KR",
    "de-DE", "fr-FR", "es-ES", "pt-BR", "ru-RU", "it-IT",
    "nl-NL", "sv-SE", "pl-PL", "tr-TR", "ar-SA", "hi-IN"
]

PLATFORMS = ["Win32", "Linux x86_64", "MacIntel"]

used_noise_seeds = set()


def generate_unique_noise():
    while True:
        noise = round(random.uniform(0.0001, 0.01), 6)
        if noise not in used_noise_seeds:
            used_noise_seeds.add(noise)
            return noise


def generate_random_profile():
    webgl = random.choice(WEBGL_CONFIGS)
    return {
        "platform": random.choice(PLATFORMS),
        "hardwareConcurrency": random.choice([2, 4, 6, 8, 10, 12, 16]),
        "deviceMemory": random.choice([2, 4, 8, 16, 32]),
        "maxTouchPoints": 0,
        "webgl_vendor": webgl["vendor"],
        "webgl_renderer": webgl["renderer"],
        "canvas_noise": generate_unique_noise(),
        "webgl_noise": generate_unique_noise(),
        "audio_noise": generate_unique_noise(),
        "clientRects_noise": generate_unique_noise(),
        "webrtc_ip": f"{random.randint(10,192)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
        "timezone": random.choice(TIMEZONES),
        "language": random.choice(LANGUAGES),
    }


class Api:
    def __init__(self):
        self.profiles = load_profiles()
        self.running_processes = {}
        self._monitor_thread = threading.Thread(target=self._monitor_processes, daemon=True)
        self._monitor_thread.start()

    def _monitor_processes(self):
        while True:
            to_remove = []
            for pid, proc in self.running_processes.items():
                if proc.poll() is not None:
                    to_remove.append(pid)
            for pid in to_remove:
                del self.running_processes[pid]
                for p_id, p_data in self.profiles.items():
                    if p_data.get("pid") == pid:
                        p_data["status"] = "stopped"
                        p_data["pid"] = None
                        save_profiles(self.profiles)
                        break
            time.sleep(1)

    def get_profiles(self):
        self.profiles = load_profiles()
        # 检查运行状态
        for p_id, p_data in self.profiles.items():
            pid = p_data.get("pid")
            if pid and pid in self.running_processes:
                if self.running_processes[pid].poll() is None:
                    p_data["status"] = "running"
                else:
                    p_data["status"] = "stopped"
                    p_data["pid"] = None
                    del self.running_processes[pid]
            else:
                p_data["status"] = "stopped"
                p_data["pid"] = None
        save_profiles(self.profiles)
        result = []
        for p_id, p_data in self.profiles.items():
            result.append({**p_data, "id": p_id})
        return result

    def get_random_profile(self):
        return generate_random_profile()

    def get_webgl_configs(self):
        return WEBGL_CONFIGS

    def get_timezones(self):
        return TIMEZONES

    def get_languages(self):
        return LANGUAGES

    def get_platforms(self):
        return PLATFORMS

    def create_profile(self, name, config):
        profile_id = str(uuid.uuid4())[:8]
        user_data_dir = os.path.join(PROFILES_DIR, profile_id)
        os.makedirs(user_data_dir, exist_ok=True)

        profile_data = {
            "name": name,
            "config": config,
            "user_data_dir": user_data_dir,
            "status": "stopped",
            "pid": None,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.profiles[profile_id] = profile_data
        save_profiles(self.profiles)
        return {"success": True, "id": profile_id}

    def update_profile(self, profile_id, name, config):
        if profile_id in self.profiles:
            if self.profiles[profile_id].get("status") == "running":
                return {"success": False, "error": "无法编辑正在运行的环境"}
            self.profiles[profile_id]["name"] = name
            self.profiles[profile_id]["config"] = config
            save_profiles(self.profiles)
            return {"success": True}
        return {"success": False, "error": "环境不存在"}

    def delete_profile(self, profile_id):
        if profile_id in self.profiles:
            if self.profiles[profile_id].get("status") == "running":
                return {"success": False, "error": "无法删除正在运行的环境，请先停止"}
            user_data_dir = self.profiles[profile_id].get("user_data_dir", "")
            if os.path.exists(user_data_dir):
                import shutil
                shutil.rmtree(user_data_dir, ignore_errors=True)
            del self.profiles[profile_id]
            save_profiles(self.profiles)
            return {"success": True}
        return {"success": False, "error": "环境不存在"}

    def start_profile(self, profile_id):
        if profile_id not in self.profiles:
            return {"success": False, "error": "环境不存在"}

        profile = self.profiles[profile_id]
        if profile.get("status") == "running":
            return {"success": False, "error": "环境已在运行中"}

        config = profile["config"]
        user_data_dir = profile["user_data_dir"]

        args = [CHROME_PATH]
        args.append(f'--user-data-dir={user_data_dir}')

        if config.get("platform"):
            args.append(f'--fingerprint-platform={config["platform"]}')
        if config.get("hardwareConcurrency"):
            args.append(f'--fingerprint-hardwareConcurrency={config["hardwareConcurrency"]}')
        if config.get("deviceMemory"):
            args.append(f'--fingerprint-deviceMemory={config["deviceMemory"]}')
        if config.get("maxTouchPoints") is not None:
            args.append(f'--fingerprint-maxTouchPoints={config["maxTouchPoints"]}')
        if config.get("webgl_vendor"):
            args.append(f'--fingerprint-webgl-vendor={config["webgl_vendor"]}')
        if config.get("webgl_renderer"):
            args.append(f'--fingerprint-webgl-renderer={config["webgl_renderer"]}')
        if config.get("canvas_noise"):
            args.append(f'--fingerprint-canvas-noise={config["canvas_noise"]}')
        if config.get("webgl_noise"):
            args.append(f'--fingerprint-webgl-noise={config["webgl_noise"]}')
        if config.get("audio_noise"):
            args.append(f'--fingerprint-audio-noise={config["audio_noise"]}')
        if config.get("clientRects_noise"):
            args.append(f'--fingerprint-clientRects-noise={config["clientRects_noise"]}')
        if config.get("webrtc_ip"):
            args.append(f'--fingerprint-webrtc-ip={config["webrtc_ip"]}')
        if config.get("timezone"):
            args.append(f'--fingerprint-timezone={config["timezone"]}')
        if config.get("language"):
            args.append(f'--fingerprint-language={config["language"]}')

        try:
            CREATE_NO_WINDOW = 0x08000000
            proc = subprocess.Popen(args, creationflags=CREATE_NO_WINDOW)
            pid = proc.pid
            self.running_processes[pid] = proc
            profile["status"] = "running"
            profile["pid"] = pid
            save_profiles(self.profiles)
            return {"success": True, "pid": pid}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def stop_profile(self, profile_id):
        if profile_id not in self.profiles:
            return {"success": False, "error": "环境不存在"}

        profile = self.profiles[profile_id]
        pid = profile.get("pid")

        if pid and pid in self.running_processes:
            proc = self.running_processes[pid]
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                del self.running_processes[pid]
            except Exception:
                pass

        profile["status"] = "stopped"
        profile["pid"] = None
        save_profiles(self.profiles)
        return {"success": True}

    def get_profile_detail(self, profile_id):
        if profile_id in self.profiles:
            return {**self.profiles[profile_id], "id": profile_id}
        return None


HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>指纹浏览器管理器</title>
<style>
*, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }

:root {
    --bg: #0f1117;
    --bg2: #1a1d27;
    --bg3: #242836;
    --bg4: #2d3245;
    --accent: #6c5ce7;
    --accent2: #a29bfe;
    --accent3: #7c6ff7;
    --green: #00b894;
    --green2: #55efc4;
    --red: #e17055;
    --red2: #ff7675;
    --yellow: #fdcb6e;
    --text: #e8e8ed;
    --text2: #a0a3b1;
    --text3: #6c7086;
    --border: #2d3245;
    --shadow: 0 8px 32px rgba(0,0,0,0.3);
    --radius: 16px;
    --radius-sm: 10px;
    --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    overflow-x: hidden;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--bg4); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent); }

/* Header */
.header {
    background: linear-gradient(135deg, var(--bg2) 0%, var(--bg3) 100%);
    border-bottom: 1px solid var(--border);
    padding: 20px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 100;
    backdrop-filter: blur(20px);
}

.header-left {
    display: flex;
    align-items: center;
    gap: 14px;
}

.logo {
    width: 42px;
    height: 42px;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    box-shadow: 0 4px 15px rgba(108,92,231,0.3);
}

.header h1 {
    font-size: 22px;
    font-weight: 700;
    background: linear-gradient(135deg, var(--text), var(--accent2));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.header-right {
    display: flex;
    align-items: center;
    gap: 12px;
}

.stats {
    display: flex;
    gap: 20px;
    margin-right: 16px;
}

.stat-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: var(--text2);
}

.stat-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
}

.stat-dot.green { background: var(--green); box-shadow: 0 0 8px var(--green); }
.stat-dot.gray { background: var(--text3); }

/* Buttons */
.btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 20px;
    border: none;
    border-radius: var(--radius-sm);
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: var(--transition);
    outline: none;
    white-space: nowrap;
}

.btn-primary {
    background: linear-gradient(135deg, var(--accent), var(--accent3));
    color: white;
    box-shadow: 0 4px 15px rgba(108,92,231,0.3);
}
.btn-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(108,92,231,0.4);
}

.btn-success {
    background: linear-gradient(135deg, var(--green), #00d2a0);
    color: white;
    box-shadow: 0 4px 15px rgba(0,184,148,0.3);
}
.btn-success:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0,184,148,0.4);
}

.btn-danger {
    background: linear-gradient(135deg, var(--red), var(--red2));
    color: white;
}
.btn-danger:hover { transform: translateY(-2px); }

.btn-ghost {
    background: var(--bg3);
    color: var(--text2);
    border: 1px solid var(--border);
}
.btn-ghost:hover {
    background: var(--bg4);
    color: var(--text);
    border-color: var(--accent);
}

.btn-sm {
    padding: 6px 14px;
    font-size: 12px;
    border-radius: 8px;
}

.btn-icon {
    width: 36px;
    height: 36px;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 10px;
}

/* Main Content */
.main {
    padding: 28px 32px;
    max-width: 1600px;
    margin: 0 auto;
}

/* Search Bar */
.toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 24px;
}

.search-box {
    flex: 1;
    position: relative;
}

.search-box input {
    width: 100%;
    padding: 12px 16px 12px 44px;
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text);
    font-size: 14px;
    transition: var(--transition);
    outline: none;
}

.search-box input:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(108,92,231,0.15);
}

.search-box input::placeholder { color: var(--text3); }

.search-box .search-icon {
    position: absolute;
    left: 14px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text3);
    font-size: 16px;
}

/* Grid */
.grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 20px;
}

/* Card */
.card {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 22px;
    transition: var(--transition);
    position: relative;
    overflow: hidden;
}

.card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    opacity: 0;
    transition: var(--transition);
}

.card:hover {
    border-color: var(--accent);
    transform: translateY(-3px);
    box-shadow: var(--shadow);
}

.card:hover::before { opacity: 1; }

.card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
}

.card-title-group {
    display: flex;
    align-items: center;
    gap: 12px;
    flex: 1;
    min-width: 0;
}

.card-avatar {
    width: 42px;
    height: 42px;
    border-radius: 12px;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 16px;
    color: white;
    flex-shrink: 0;
}

.card-name {
    font-size: 16px;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.card-id {
    font-size: 11px;
    color: var(--text3);
    font-family: monospace;
}

.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    flex-shrink: 0;
}

.status-badge.running {
    background: rgba(0,184,148,0.12);
    color: var(--green2);
}

.status-badge.running .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 8px var(--green);
    animation: pulse 2s infinite;
}

.status-badge.stopped {
    background: rgba(108,112,134,0.15);
    color: var(--text3);
}

.status-badge.stopped .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--text3);
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
}

.card-info {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-bottom: 18px;
}

.info-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.info-label {
    font-size: 11px;
    color: var(--text3);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.info-value {
    font-size: 13px;
    color: var(--text2);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.card-actions {
    display: flex;
    gap: 8px;
}

.card-actions .btn { flex: 1; justify-content: center; }

/* Modal */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0,0,0,0.6);
    backdrop-filter: blur(8px);
    display: none;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 20px;
}

.modal-overlay.active { display: flex; }

.modal {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 20px;
    width: 100%;
    max-width: 720px;
    max-height: 85vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    box-shadow: 0 25px 60px rgba(0,0,0,0.5);
    animation: modalIn 0.3s ease;
}

@keyframes modalIn {
    from { transform: scale(0.9) translateY(20px); opacity: 0; }
    to { transform: scale(1) translateY(0); opacity: 1; }
}

.modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 22px 28px;
    border-bottom: 1px solid var(--border);
}

.modal-header h2 {
    font-size: 20px;
    font-weight: 700;
}

.modal-close {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    background: var(--bg3);
    color: var(--text2);
    border-radius: 10px;
    cursor: pointer;
    font-size: 18px;
    transition: var(--transition);
}

.modal-close:hover {
    background: var(--red);
    color: white;
}

.modal-body {
    padding: 24px 28px;
    overflow-y: auto;
    flex: 1;
}

.modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    padding: 18px 28px;
    border-top: 1px solid var(--border);
}

/* Form */
.form-group {
    margin-bottom: 18px;
}

.form-label {
    display: block;
    font-size: 13px;
    font-weight: 600;
    color: var(--text2);
    margin-bottom: 6px;
}

.form-input, .form-select {
    width: 100%;
    padding: 10px 14px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text);
    font-size: 14px;
    transition: var(--transition);
    outline: none;
}

.form-input:focus, .form-select:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(108,92,231,0.15);
}

.form-select {
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23a0a3b1' d='M6 8L1 3h10z'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 12px center;
    padding-right: 32px;
}

.form-select option {
    background: var(--bg2);
    color: var(--text);
}

.form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
}

.form-section {
    margin-bottom: 22px;
}

.form-section-title {
    font-size: 14px;
    font-weight: 700;
    color: var(--accent2);
    margin-bottom: 14px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 8px;
}

.randomize-btn {
    margin-left: auto;
    padding: 4px 12px;
    font-size: 11px;
    background: var(--bg3);
    border: 1px solid var(--border);
    color: var(--accent2);
    border-radius: 6px;
    cursor: pointer;
    transition: var(--transition);
}

.randomize-btn:hover {
    background: var(--accent);
    color: white;
    border-color: var(--accent);
}

/* Empty State */
.empty-state {
    text-align: center;
    padding: 80px 20px;
    color: var(--text3);
}

.empty-icon {
    font-size: 64px;
    margin-bottom: 16px;
    opacity: 0.5;
}

.empty-state h3 {
    font-size: 20px;
    color: var(--text2);
    margin-bottom: 8px;
}

.empty-state p {
    font-size: 14px;
    margin-bottom: 24px;
}

/* Toast */
.toast-container {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 2000;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.toast {
    padding: 14px 20px;
    border-radius: var(--radius-sm);
    font-size: 14px;
    font-weight: 500;
    box-shadow: var(--shadow);
    animation: toastIn 0.3s ease;
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 280px;
}

.toast.success {
    background: linear-gradient(135deg, rgba(0,184,148,0.9), rgba(0,210,160,0.9));
    color: white;
}

.toast.error {
    background: linear-gradient(135deg, rgba(225,112,85,0.9), rgba(255,118,117,0.9));
    color: white;
}

.toast.info {
    background: linear-gradient(135deg, rgba(108,92,231,0.9), rgba(124,111,247,0.9));
    color: white;
}

@keyframes toastIn {
    from { transform: translateX(100px); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
}

/* Confirm Dialog */
.confirm-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.6);
    backdrop-filter: blur(8px);
    display: none;
    align-items: center;
    justify-content: center;
    z-index: 1500;
}

.confirm-overlay.active { display: flex; }

.confirm-box {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 28px;
    max-width: 400px;
    width: 90%;
    text-align: center;
    box-shadow: 0 25px 60px rgba(0,0,0,0.5);
    animation: modalIn 0.3s ease;
}

.confirm-box h3 { margin-bottom: 10px; font-size: 18px; }
.confirm-box p { color: var(--text2); font-size: 14px; margin-bottom: 24px; }
.confirm-actions { display: flex; gap: 10px; justify-content: center; }

/* Responsive */
@media (max-width: 768px) {
    .header { padding: 16px 20px; }
    .main { padding: 20px; }
    .grid { grid-template-columns: 1fr; }
    .form-row { grid-template-columns: 1fr; }
    .stats { display: none; }
    .toolbar { flex-wrap: wrap; }
}
</style>
</head>
<body>

<div class="header">
    <div class="header-left">
        <div class="logo">🌐</div>
        <h1>指纹浏览器管理器</h1>
        <label class="form-label">by Zeb</label>
    </div>
    <div class="header-right">
        <div class="stats">
            <div class="stat-item">
                <span class="stat-dot green"></span>
                <span>运行中: <strong id="runningCount">0</strong></span>
            </div>
            <div class="stat-item">
                <span class="stat-dot gray"></span>
                <span>总数: <strong id="totalCount">0</strong></span>
            </div>
        </div>
        <button class="btn btn-primary" onclick="openCreateModal()">
            <span>＋</span> 新建环境
        </button>
    </div>
</div>

<div class="main">
    <div class="toolbar">
        <div class="search-box">
            <span class="search-icon">🔍</span>
            <input type="text" id="searchInput" placeholder="搜索环境名称或ID..." oninput="filterProfiles()">
        </div>
        <button class="btn btn-ghost" onclick="refreshProfiles()">🔄 刷新</button>
    </div>
    <div class="grid" id="profileGrid"></div>
</div>

<!-- Create/Edit Modal -->
<div class="modal-overlay" id="profileModal">
    <div class="modal">
        <div class="modal-header">
            <h2 id="modalTitle">新建环境</h2>
            <button class="modal-close" onclick="closeModal()">✕</button>
        </div>
        <div class="modal-body">
            <div class="form-section">
                <div class="form-section-title">
                    <span>📋</span> 基本信息
                </div>
                <div class="form-group">
                    <label class="form-label">环境名称 *</label>
                    <input type="text" class="form-input" id="profileName" placeholder="输入环境名称">
                </div>
            </div>

            <div class="form-section">
                <div class="form-section-title">
                    <span>🖥️</span> 系统信息
                    <button class="randomize-btn" onclick="randomizeAll()">🎲 全部随机</button>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">平台 (Platform)</label>
                        <select class="form-select" id="fp_platform">
                            <option value="">随机</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">CPU 核心数</label>
                        <select class="form-select" id="fp_hardwareConcurrency">
                            <option value="">随机</option>
                            <option value="2">2</option>
                            <option value="4">4</option>
                            <option value="6">6</option>
                            <option value="8">8</option>
                            <option value="10">10</option>
                            <option value="12">12</option>
                            <option value="16">16</option>
                        </select>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">设备内存 (GB)</label>
                        <select class="form-select" id="fp_deviceMemory">
                            <option value="">随机</option>
                            <option value="2">2</option>
                            <option value="4">4</option>
                            <option value="8">8</option>
                            <option value="16">16</option>
                            <option value="32">32</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">最大触摸点数</label>
                        <select class="form-select" id="fp_maxTouchPoints">
                            <option value="">随机</option>
                            <option value="0">0 (无触摸)</option>
                            <option value="1">1</option>
                            <option value="5">5</option>
                            <option value="10">10</option>
                        </select>
                    </div>
                </div>
            </div>

            <div class="form-section">
                <div class="form-section-title">
                    <span>🎮</span> WebGL 配置
                </div>
                <div class="form-group">
                    <label class="form-label">WebGL 供应商</label>
                    <input type="text" class="form-input" id="fp_webgl_vendor" placeholder="随机生成">
                </div>
                <div class="form-group">
                    <label class="form-label">WebGL 渲染器</label>
                    <input type="text" class="form-input" id="fp_webgl_renderer" placeholder="随机生成">
                </div>
                <div class="form-group">
                    <label class="form-label">WebGL 预设</label>
                    <select class="form-select" id="webglPreset" onchange="applyWebGLPreset()">
                        <option value="">自定义 / 随机</option>
                    </select>
                </div>
            </div>

            <div class="form-section">
                <div class="form-section-title">
                    <span>🔊</span> 噪声参数
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Canvas 噪声</label>
                        <input type="text" class="form-input" id="fp_canvas_noise" placeholder="随机 (0.0001~0.01)">
                    </div>
                    <div class="form-group">
                        <label class="form-label">WebGL 噪声</label>
                        <input type="text" class="form-input" id="fp_webgl_noise" placeholder="随机 (0.0001~0.01)">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Audio 噪声</label>
                        <input type="text" class="form-input" id="fp_audio_noise" placeholder="随机 (0.0001~0.01)">
                    </div>
                    <div class="form-group">
                        <label class="form-label">ClientRects 噪声</label>
                        <input type="text" class="form-input" id="fp_clientRects_noise" placeholder="随机 (0.0001~0.01)">
                    </div>
                </div>
            </div>

            <div class="form-section">
                <div class="form-section-title">
                    <span>🌍</span> 网络与地区
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">WebRTC IP</label>
                        <input type="text" class="form-input" id="fp_webrtc_ip" placeholder="随机生成">
                    </div>
                    <div class="form-group">
                        <label class="form-label">时区</label>
                        <select class="form-select" id="fp_timezone">
                            <option value="">随机</option>
                        </select>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">语言</label>
                        <select class="form-select" id="fp_language">
                            <option value="">随机</option>
                        </select>
                    </div>
                    <div class="form-group"></div>
                </div>
            </div>
        </div>
        <div class="modal-footer">
            <button class="btn btn-ghost" onclick="closeModal()">取消</button>
            <button class="btn btn-primary" id="modalSaveBtn" onclick="saveProfile()">创建环境</button>
        </div>
    </div>
</div>

<!-- Detail Modal -->
<div class="modal-overlay" id="detailModal">
    <div class="modal">
        <div class="modal-header">
            <h2>环境详情</h2>
            <button class="modal-close" onclick="closeDetailModal()">✕</button>
        </div>
        <div class="modal-body" id="detailBody"></div>
        <div class="modal-footer">
            <button class="btn btn-ghost" onclick="closeDetailModal()">关闭</button>
        </div>
    </div>
</div>

<!-- Confirm Dialog -->
<div class="confirm-overlay" id="confirmOverlay">
    <div class="confirm-box">
        <h3 id="confirmTitle">确认操作</h3>
        <p id="confirmMessage">确定要执行此操作吗？</p>
        <div class="confirm-actions">
            <button class="btn btn-ghost" onclick="closeConfirm()">取消</button>
            <button class="btn btn-danger" id="confirmBtn" onclick="confirmAction()">确认</button>
        </div>
    </div>
</div>

<div class="toast-container" id="toastContainer"></div>

<script>
let allProfiles = [];
let editingId = null;
let pendingConfirmAction = null;
let webglConfigs = [];
let timezones = [];
let languages = [];
let platforms = [];

// Init
async function init() {
    platforms = await pywebview.api.get_platforms();
    timezones = await pywebview.api.get_timezones();
    languages = await pywebview.api.get_languages();
    webglConfigs = await pywebview.api.get_webgl_configs();

    const platformSel = document.getElementById('fp_platform');
    platforms.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p; opt.textContent = p;
        platformSel.appendChild(opt);
    });

    const tzSel = document.getElementById('fp_timezone');
    timezones.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t; opt.textContent = t;
        tzSel.appendChild(opt);
    });

    const langSel = document.getElementById('fp_language');
    languages.forEach(l => {
        const opt = document.createElement('option');
        opt.value = l; opt.textContent = l;
        langSel.appendChild(opt);
    });

    const presetSel = document.getElementById('webglPreset');
    webglConfigs.forEach((c, i) => {
        const opt = document.createElement('option');
        opt.value = i;
        const shortRenderer = c.renderer.length > 60 ? c.renderer.substring(0, 60) + '...' : c.renderer;
        opt.textContent = shortRenderer;
        presetSel.appendChild(opt);
    });

    refreshProfiles();
    setInterval(refreshProfiles, 3000);
}

function applyWebGLPreset() {
    const idx = document.getElementById('webglPreset').value;
    if (idx !== '') {
        const config = webglConfigs[parseInt(idx)];
        document.getElementById('fp_webgl_vendor').value = config.vendor;
        document.getElementById('fp_webgl_renderer').value = config.renderer;
    }
}

async function randomizeAll() {
    const rnd = await pywebview.api.get_random_profile();
    document.getElementById('fp_platform').value = rnd.platform;
    document.getElementById('fp_hardwareConcurrency').value = rnd.hardwareConcurrency;
    document.getElementById('fp_deviceMemory').value = rnd.deviceMemory;
    document.getElementById('fp_maxTouchPoints').value = rnd.maxTouchPoints;
    document.getElementById('fp_webgl_vendor').value = rnd.webgl_vendor;
    document.getElementById('fp_webgl_renderer').value = rnd.webgl_renderer;
    document.getElementById('fp_canvas_noise').value = rnd.canvas_noise;
    document.getElementById('fp_webgl_noise').value = rnd.webgl_noise;
    document.getElementById('fp_audio_noise').value = rnd.audio_noise;
    document.getElementById('fp_clientRects_noise').value = rnd.clientRects_noise;
    document.getElementById('fp_webrtc_ip').value = rnd.webrtc_ip;
    document.getElementById('fp_timezone').value = rnd.timezone;
    document.getElementById('fp_language').value = rnd.language;
    document.getElementById('webglPreset').value = '';
    showToast('已随机生成所有参数', 'info');
}

async function refreshProfiles() {
    allProfiles = await pywebview.api.get_profiles();
    renderProfiles();
    updateStats();
}

function updateStats() {
    const running = allProfiles.filter(p => p.status === 'running').length;
    document.getElementById('runningCount').textContent = running;
    document.getElementById('totalCount').textContent = allProfiles.length;
}

function filterProfiles() {
    renderProfiles();
}

function renderProfiles() {
    const query = document.getElementById('searchInput').value.toLowerCase();
    const grid = document.getElementById('profileGrid');
    let filtered = allProfiles;

    if (query) {
        filtered = filtered.filter(p =>
            p.name.toLowerCase().includes(query) ||
            p.id.toLowerCase().includes(query)
        );
    }

    if (filtered.length === 0) {
        grid.innerHTML = `
            <div class="empty-state" style="grid-column: 1/-1;">
                <div class="empty-icon">📁</div>
                <h3>${query ? '未找到匹配的环境' : '还没有任何环境'}</h3>
                <p>${query ? '尝试使用其他关键词搜索' : '点击上方"新建环境"按钮创建你的第一个浏览器环境'}</p>
                ${!query ? '<button class="btn btn-primary" onclick="openCreateModal()">＋ 新建环境</button>' : ''}
            </div>
        `;
        return;
    }

    grid.innerHTML = filtered.map(p => {
        const isRunning = p.status === 'running';
        const cfg = p.config || {};
        const initial = (p.name || '?')[0].toUpperCase();
        const avatarColors = [
            'linear-gradient(135deg, #6c5ce7, #a29bfe)',
            'linear-gradient(135deg, #00b894, #55efc4)',
            'linear-gradient(135deg, #e17055, #ff7675)',
            'linear-gradient(135deg, #fdcb6e, #f39c12)',
            'linear-gradient(135deg, #0984e3, #74b9ff)',
            'linear-gradient(135deg, #e84393, #fd79a8)',
        ];
        const colorIdx = p.id.charCodeAt(0) % avatarColors.length;

        return `
        <div class="card">
            <div class="card-header">
                <div class="card-title-group">
                    <div class="card-avatar" style="background:${avatarColors[colorIdx]}">${initial}</div>
                    <div>
                        <div class="card-name">${escapeHtml(p.name)}</div>
                        <div class="card-id">#${p.id}</div>
                    </div>
                </div>
                <div class="status-badge ${isRunning ? 'running' : 'stopped'}">
                    <span class="status-dot"></span>
                    ${isRunning ? '运行中' : '已停止'}
                </div>
            </div>
            <div class="card-info">
                <div class="info-item">
                    <span class="info-label">平台</span>
                    <span class="info-value">${cfg.platform || '-'}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">CPU / 内存</span>
                    <span class="info-value">${cfg.hardwareConcurrency || '-'}核 / ${cfg.deviceMemory || '-'}GB</span>
                </div>
                <div class="info-item">
                    <span class="info-label">语言</span>
                    <span class="info-value">${cfg.language || '-'}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">时区</span>
                    <span class="info-value">${cfg.timezone || '-'}</span>
                </div>
            </div>
            <div class="card-actions">
                ${isRunning
                    ? `<button class="btn btn-danger btn-sm" onclick="stopProfile('${p.id}')">⏹ 停止</button>`
                    : `<button class="btn btn-success btn-sm" onclick="startProfile('${p.id}')">▶ 启动</button>`
                }
                <button class="btn btn-ghost btn-sm" onclick="viewDetail('${p.id}')">📋 详情</button>
                <button class="btn btn-ghost btn-sm" onclick="openEditModal('${p.id}')" ${isRunning ? 'disabled style="opacity:0.4;pointer-events:none;"' : ''}>✏️ 编辑</button>
                <button class="btn btn-ghost btn-sm" onclick="confirmDelete('${p.id}')" ${isRunning ? 'disabled style="opacity:0.4;pointer-events:none;"' : ''}>🗑</button>
            </div>
        </div>
        `;
    }).join('');
}

function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

// Modal
function openCreateModal() {
    editingId = null;
    document.getElementById('modalTitle').textContent = '新建环境';
    document.getElementById('modalSaveBtn').textContent = '创建环境';
    clearForm();
    randomizeAll();
    document.getElementById('profileModal').classList.add('active');
}

async function openEditModal(id) {
    editingId = id;
    document.getElementById('modalTitle').textContent = '编辑环境';
    document.getElementById('modalSaveBtn').textContent = '保存修改';
    const detail = await pywebview.api.get_profile_detail(id);
    if (!detail) {
        showToast('环境不存在', 'error');
        return;
    }
    const cfg = detail.config || {};
    document.getElementById('profileName').value = detail.name || '';
    document.getElementById('fp_platform').value = cfg.platform || '';
    document.getElementById('fp_hardwareConcurrency').value = cfg.hardwareConcurrency || '';
    document.getElementById('fp_deviceMemory').value = cfg.deviceMemory || '';
    document.getElementById('fp_maxTouchPoints').value = cfg.maxTouchPoints != null ? cfg.maxTouchPoints : '';
    document.getElementById('fp_webgl_vendor').value = cfg.webgl_vendor || '';
    document.getElementById('fp_webgl_renderer').value = cfg.webgl_renderer || '';
    document.getElementById('fp_canvas_noise').value = cfg.canvas_noise || '';
    document.getElementById('fp_webgl_noise').value = cfg.webgl_noise || '';
    document.getElementById('fp_audio_noise').value = cfg.audio_noise || '';
    document.getElementById('fp_clientRects_noise').value = cfg.clientRects_noise || '';
    document.getElementById('fp_webrtc_ip').value = cfg.webrtc_ip || '';
    document.getElementById('fp_timezone').value = cfg.timezone || '';
    document.getElementById('fp_language').value = cfg.language || '';
    document.getElementById('webglPreset').value = '';
    document.getElementById('profileModal').classList.add('active');
}

function closeModal() {
    document.getElementById('profileModal').classList.remove('active');
    editingId = null;
}

function clearForm() {
    document.getElementById('profileName').value = '';
    document.getElementById('fp_platform').value = '';
    document.getElementById('fp_hardwareConcurrency').value = '';
    document.getElementById('fp_deviceMemory').value = '';
    document.getElementById('fp_maxTouchPoints').value = '';
    document.getElementById('fp_webgl_vendor').value = '';
    document.getElementById('fp_webgl_renderer').value = '';
    document.getElementById('fp_canvas_noise').value = '';
    document.getElementById('fp_webgl_noise').value = '';
    document.getElementById('fp_audio_noise').value = '';
    document.getElementById('fp_clientRects_noise').value = '';
    document.getElementById('fp_webrtc_ip').value = '';
    document.getElementById('fp_timezone').value = '';
    document.getElementById('fp_language').value = '';
    document.getElementById('webglPreset').value = '';
}

async function saveProfile() {
    const name = document.getElementById('profileName').value.trim();
    if (!name) {
        showToast('请输入环境名称', 'error');
        document.getElementById('profileName').focus();
        return;
    }

    const getVal = id => document.getElementById(id).value;

    const config = {};
    if (getVal('fp_platform')) config.platform = getVal('fp_platform');
    if (getVal('fp_hardwareConcurrency')) config.hardwareConcurrency = parseInt(getVal('fp_hardwareConcurrency'));
    if (getVal('fp_deviceMemory')) config.deviceMemory = parseInt(getVal('fp_deviceMemory'));
    if (getVal('fp_maxTouchPoints') !== '') config.maxTouchPoints = parseInt(getVal('fp_maxTouchPoints'));
    if (getVal('fp_webgl_vendor')) config.webgl_vendor = getVal('fp_webgl_vendor');
    if (getVal('fp_webgl_renderer')) config.webgl_renderer = getVal('fp_webgl_renderer');
    if (getVal('fp_canvas_noise')) config.canvas_noise = parseFloat(getVal('fp_canvas_noise'));
    if (getVal('fp_webgl_noise')) config.webgl_noise = parseFloat(getVal('fp_webgl_noise'));
    if (getVal('fp_audio_noise')) config.audio_noise = parseFloat(getVal('fp_audio_noise'));
    if (getVal('fp_clientRects_noise')) config.clientRects_noise = parseFloat(getVal('fp_clientRects_noise'));
    if (getVal('fp_webrtc_ip')) config.webrtc_ip = getVal('fp_webrtc_ip');
    if (getVal('fp_timezone')) config.timezone = getVal('fp_timezone');
    if (getVal('fp_language')) config.language = getVal('fp_language');

    // 没填的参数用随机值
    const rnd = await pywebview.api.get_random_profile();
    if (!config.platform) config.platform = rnd.platform;
    if (!config.hardwareConcurrency) config.hardwareConcurrency = rnd.hardwareConcurrency;
    if (!config.deviceMemory) config.deviceMemory = rnd.deviceMemory;
    if (config.maxTouchPoints == null || isNaN(config.maxTouchPoints)) config.maxTouchPoints = rnd.maxTouchPoints;
    if (!config.webgl_vendor) config.webgl_vendor = rnd.webgl_vendor;
    if (!config.webgl_renderer) config.webgl_renderer = rnd.webgl_renderer;
    if (!config.canvas_noise) config.canvas_noise = rnd.canvas_noise;
    if (!config.webgl_noise) config.webgl_noise = rnd.webgl_noise;
    if (!config.audio_noise) config.audio_noise = rnd.audio_noise;
    if (!config.clientRects_noise) config.clientRects_noise = rnd.clientRects_noise;
    if (!config.webrtc_ip) config.webrtc_ip = rnd.webrtc_ip;
    if (!config.timezone) config.timezone = rnd.timezone;
    if (!config.language) config.language = rnd.language;

    let result;
    if (editingId) {
        result = await pywebview.api.update_profile(editingId, name, config);
    } else {
        result = await pywebview.api.create_profile(name, config);
    }

    if (result.success) {
        showToast(editingId ? '环境已更新' : '环境创建成功', 'success');
        closeModal();
        refreshProfiles();
    } else {
        showToast(result.error || '操作失败', 'error');
    }
}

// Actions
async function startProfile(id) {
    const result = await pywebview.api.start_profile(id);
    if (result.success) {
        showToast('浏览器环境已启动', 'success');
        refreshProfiles();
    } else {
        showToast(result.error || '启动失败', 'error');
    }
}

async function stopProfile(id) {
    const result = await pywebview.api.stop_profile(id);
    if (result.success) {
        showToast('浏览器环境已停止', 'success');
        refreshProfiles();
    } else {
        showToast(result.error || '停止失败', 'error');
    }
}

function confirmDelete(id) {
    const profile = allProfiles.find(p => p.id === id);
    document.getElementById('confirmTitle').textContent = '删除环境';
    document.getElementById('confirmMessage').textContent = `确定要删除环境 "${profile ? profile.name : id}" 吗？此操作将删除所有浏览器数据且不可恢复。`;
    pendingConfirmAction = async () => {
        const result = await pywebview.api.delete_profile(id);
        if (result.success) {
            showToast('环境已删除', 'success');
            refreshProfiles();
        } else {
            showToast(result.error || '删除失败', 'error');
        }
    };
    document.getElementById('confirmOverlay').classList.add('active');
}

function confirmAction() {
    if (pendingConfirmAction) {
        pendingConfirmAction();
        pendingConfirmAction = null;
    }
    closeConfirm();
}

function closeConfirm() {
    document.getElementById('confirmOverlay').classList.remove('active');
}

// Detail
async function viewDetail(id) {
    const detail = await pywebview.api.get_profile_detail(id);
    if (!detail) {
        showToast('环境不存在', 'error');
        return;
    }
    const cfg = detail.config || {};
    const isRunning = detail.status === 'running';
    document.getElementById('detailBody').innerHTML = `
        <div style="display:flex;align-items:center;gap:16px;margin-bottom:24px;">
            <div style="width:56px;height:56px;border-radius:16px;background:linear-gradient(135deg,var(--accent),var(--accent2));display:flex;align-items:center;justify-content:center;font-size:24px;font-weight:700;color:white;">
                ${(detail.name || '?')[0].toUpperCase()}
            </div>
            <div>
                <div style="font-size:20px;font-weight:700;">${escapeHtml(detail.name)}</div>
                <div style="font-size:13px;color:var(--text3);font-family:monospace;">#${detail.id}</div>
            </div>
            <div class="status-badge ${isRunning ? 'running' : 'stopped'}" style="margin-left:auto;">
                <span class="status-dot"></span>
                ${isRunning ? '运行中' : '已停止'}
            </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
            ${detailItem('平台', cfg.platform)}
            ${detailItem('CPU 核心数', cfg.hardwareConcurrency)}
            ${detailItem('设备内存', cfg.deviceMemory ? cfg.deviceMemory + ' GB' : '-')}
            ${detailItem('触摸点数', cfg.maxTouchPoints)}
            ${detailItem('WebGL 供应商', cfg.webgl_vendor, true)}
            ${detailItem('WebGL 渲染器', cfg.webgl_renderer, true)}
            ${detailItem('Canvas 噪声', cfg.canvas_noise)}
            ${detailItem('WebGL 噪声', cfg.webgl_noise)}
            ${detailItem('Audio 噪声', cfg.audio_noise)}
            ${detailItem('ClientRects 噪声', cfg.clientRects_noise)}
            ${detailItem('WebRTC IP', cfg.webrtc_ip)}
            ${detailItem('时区', cfg.timezone)}
            ${detailItem('语言', cfg.language)}
            ${detailItem('创建时间', detail.created_at)}
        </div>
    `;
    document.getElementById('detailModal').classList.add('active');
}

function detailItem(label, value, wide) {
    return `
        <div style="${wide ? 'grid-column:1/-1;' : ''}background:var(--bg);padding:12px 16px;border-radius:10px;">
            <div style="font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;">${label}</div>
            <div style="font-size:13px;color:var(--text);word-break:break-all;">${value != null ? value : '-'}</div>
        </div>
    `;
}

function closeDetailModal() {
    document.getElementById('detailModal').classList.remove('active');
}

// Toast
function showToast(message, type) {
    const container = document.getElementById('toastContainer');
    const icons = { success: '✅', error: '❌', info: 'ℹ️' };
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${icons[type] || ''}</span> ${message}`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100px)';
        toast.style.transition = '0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Start
window.addEventListener('pywebviewready', init);
</script>
</body>
</html>
"""


if __name__ == '__main__':
    api = Api()
    window = webview.create_window(
        '指纹浏览器管理器',
        html=HTML,
        js_api=api,
        width=1280,
        height=850,
        min_size=(900, 600),
        background_color='#0f1117',
        text_select=False
    )
    webview.start(debug=False)
