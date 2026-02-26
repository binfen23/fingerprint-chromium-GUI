import webview
import json
import os
import subprocess
import uuid
import random
import psutil
import ctypes
import atexit
from datetime import datetime
import time  # 新增：用于缓存计时

# ================= 配置区域 =================
CHROME_PATH = r".\fingerprint-chromium\chrome.exe"

DATA_FILE = "profiles.json"
BASE_DATA_DIR = os.path.join(os.getcwd(), "user_data_profiles")

if not os.path.exists(BASE_DATA_DIR):
    os.makedirs(BASE_DATA_DIR)

# ================= 数据管理层（高性能优化版） =================
class ProfileManager:
    def __init__(self):
        self.profiles = self.load_profiles()
        self.running_processes = {}
        self._last_full_scan = 0          # 上次全扫描时间
        self._running_dirs_cache = set()  # 6秒缓存

    def load_profiles(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_profiles(self):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.profiles, f, indent=4, ensure_ascii=False)

    def get_running_chrome_dirs(self):
        """高效扫描（跳过无关进程，大幅降低CPU）"""
        dirs = set()
        for proc in psutil.process_iter(['pid', 'name', 'cmdline'], ad_value=None):
            try:
                name = proc.info.get('name', '').lower()
                if 'chrome' not in name:
                    continue
                cmdline = proc.info.get('cmdline') or []
                cmd_str = ' '.join(str(x) for x in cmdline)
                if '--user-data-dir=' not in cmd_str:
                    continue
                for part in cmdline:
                    if isinstance(part, str) and part.startswith('--user-data-dir='):
                        dirs.add(part.split('=', 1)[1])
                        break
            except:
                continue
        return dirs

    def check_status(self):
        """优化版状态同步：自己进程实时监控 + 全扫描每6秒一次"""
        now = time.time()

        # 每6秒才做一次完整进程扫描（CPU占用降低80%以上）
        if now - self._last_full_scan > 6.0:
            self._running_dirs_cache = self.get_running_chrome_dirs()
            self._last_full_scan = now

        # 实时检测自己启动的进程是否死亡（几乎零开销）
        dead = [pid for pid, proc in list(self.running_processes.items()) if proc.poll() is not None]
        for pid in dead:
            del self.running_processes[pid]

        # 同步所有 profile 状态
        changed = False
        running_ids = set(self.running_processes.keys())

        for p in self.profiles:
            data_dir = os.path.join(BASE_DATA_DIR, p["id"])
            actually_running = (p["id"] in running_ids or data_dir in self._running_dirs_cache)

            new_status = "running" if actually_running else "stopped"
            if p.get("status") != new_status:
                p["status"] = new_status
                changed = True

        if changed:
            self.save_profiles()

        return {pid: "running" for pid in self.running_processes}

    def create_profile(self, name, config):
        profile_id = str(uuid.uuid4())[:8]
        profile = {
            "id": profile_id,
            "name": name,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "config": config,
            "status": "stopped"
        }
        self.profiles.append(profile)
        self.save_profiles()
        return profile

    def update_profile(self, profile_id, name, config):
        for p in self.profiles:
            if p["id"] == profile_id:
                p["name"] = name
                p["config"] = config
                self.save_profiles()
                return p
        return None

    def delete_profile(self, profile_id):
        self.stop_profile(profile_id)
        data_dir = os.path.join(BASE_DATA_DIR, profile_id)
        if os.path.exists(data_dir):
            try:
                import shutil
                shutil.rmtree(data_dir)
            except:
                pass
        self.profiles = [p for p in self.profiles if p["id"] != profile_id]
        self.save_profiles()
        return True

    def start_profile(self, profile_id):
        profile = self.get_profile(profile_id)
        if not profile or profile_id in self.running_processes:
            return {"success": False, "message": "无法启动"}

        config = profile["config"]
        user_data_dir = os.path.join(BASE_DATA_DIR, profile_id)
        args = [CHROME_PATH, f"--user-data-dir={user_data_dir}"]
        if config.get("fingerprint_seed"): args.append(f"--fingerprint={config['fingerprint_seed']}")
        if config.get("ua"): args.append(f"--user-agent={config['ua']}")
        if config.get("platform"): args.append(f"--fingerprint-platform={config['platform']}")
        if config.get("brand"): args.append(f"--fingerprint-brand={config['brand']}")
        if config.get("gpu_vendor"): args.append(f"--fingerprint-gpu-vendor={config['gpu_vendor']}")
        if config.get("gpu_renderer"): args.append(f"--fingerprint-gpu-renderer={config['gpu_renderer']}")
        if config.get("cpu_cores"): args.append(f"--fingerprint-cpu-cores={config['cpu_cores']}")
        if config.get("memory_size"): args.append(f"--fingerprint-memory-size={config['memory_size']}")
        if config.get("proxy"): args.append(f"--proxy-server={config['proxy']}")
        if config.get("timezone"): args.append(f"--timezone={config['timezone']}")
        if config.get("language"): args.append(f"--lang={config['language']}")
        if config.get("geo_lat"): args.append(f"--fingerprint-geolocation-latitude={config['geo_lat']}")
        if config.get("geo_lon"): args.append(f"--fingerprint-geolocation-longitude={config['geo_lon']}")
        args.extend(["--disable-blink-features=AutomationControlled", "--no-first-run", "--no-default-browser-check"])

        try:
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
            self.running_processes[profile_id] = process
            profile["status"] = "running"
            self.save_profiles()
            self.check_status()          # 立即刷新状态
            return {"success": True, "message": "启动成功"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def stop_profile(self, profile_id):
        if profile_id in self.running_processes:
            try:
                self.running_processes[profile_id].terminate()
                self.running_processes[profile_id].wait(5)
            except:
                pass
            del self.running_processes[profile_id]

        data_dir = os.path.join(BASE_DATA_DIR, profile_id)
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                    cmd = ' '.join(str(x) for x in (proc.info.get('cmdline') or []))
                    if data_dir in cmd:
                        proc.kill()
            except:
                pass

        lock_file = os.path.join(data_dir, "SingletonLock")
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
            except:
                pass

        profile = self.get_profile(profile_id)
        if profile:
            profile["status"] = "stopped"
            self.save_profiles()
        self.check_status()              # 立即刷新状态
        return {"success": True, "message": "已停止"}

    def get_profile(self, profile_id):
        for p in self.profiles:
            if p["id"] == profile_id:
                return p
        return None

manager = ProfileManager()

# ================= API =================
class Api:
    def get_profiles(self):
        manager.check_status()
        return manager.profiles

    def create_profile(self, name, config_json):
        config = json.loads(config_json)
        return {"success": True, "data": manager.create_profile(name, config)}

    def update_profile(self, profile_id, name, config_json):
        config = json.loads(config_json)
        return {"success": True, "data": manager.update_profile(profile_id, name, config)}

    def delete_profile(self, profile_id):
        return {"success": manager.delete_profile(profile_id)}

    def start_profile(self, profile_id):
        return manager.start_profile(profile_id)

    def stop_profile(self, profile_id):
        return manager.stop_profile(profile_id)

api = Api()

# ================= 前端（最终流畅版） =================
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="zh-CN" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fingerprint Manager</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        .card { transition: all 250ms cubic-bezier(0.4, 0, 0.2, 1); }
        .card:hover { transform: translateY(-3px); box-shadow: 0 15px 25px -5px rgb(0 0 0 / 0.15); }
        .btn { transition: all 250ms cubic-bezier(0.4, 0, 0.2, 1); }
        .modal { animation: modalPop 280ms cubic-bezier(0.34, 1.56, 0.64, 1); }
        @keyframes modalPop { from { opacity: 0; transform: scale(0.92) translateY(20px); } to { opacity: 1; transform: scale(1) translateY(0); } }
        .custom-scroll::-webkit-scrollbar { width: 6px; }
        .custom-scroll::-webkit-scrollbar-thumb { background: #4b5563; border-radius: 9999px; }
        .custom-scroll::-webkit-scrollbar-thumb:hover { background: #6b7280; }
    </style>
</head>
<body class="bg-zinc-950 text-zinc-200">
    <div class="max-w-[1050px] mx-auto p-5">
        <div class="flex items-center justify-between mb-8">
            <div class="flex items-center gap-4">
                <div class="w-9 h-9 bg-gradient-to-br from-blue-500 to-violet-500 rounded-2xl flex items-center justify-center text-white font-bold text-xl">🌎️</div>
                <div>
                    <h1 class="text-1xl font-semibold tracking-tight text-white">指纹浏览器管理器</h1>
                    <p class="text-xs text-zinc-500 -mt-1">by Zeb</p>
                </div>
            </div>
            <div class="flex items-center gap-4">
                <input id="search" onkeyup="filter()" placeholder="搜索名称或ID..." 
                       class="bg-zinc-900 border border-zinc-700 focus:border-blue-500 w-80 px-4 py-2.5 rounded-2xl text-sm outline-none">
                <button onclick="openModal()" 
                        class="bg-blue-600 hover:bg-blue-500 px-6 py-2.5 rounded-2xl font-medium flex items-center gap-2 text-sm btn">
                     新建
                </button>
            </div>
        </div>
        <div id="grid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5"></div>
    </div>

    <div id="toast" class="hidden fixed bottom-6 right-6 bg-zinc-900 border border-zinc-700 rounded-2xl px-5 py-3 shadow-2xl flex items-center gap-3"></div>

    <div id="modal" class="hidden fixed inset-0 bg-black/70 flex items-center justify-center z-50">
        <div class="modal bg-zinc-900 w-full max-w-[460px] mx-4 rounded-2xl overflow-hidden border border-zinc-700">
            <div class="px-6 py-5 border-b border-zinc-700 flex items-center justify-between">
                <h2 id="modalTitle" class="text-lg font-semibold">新建环境</h2>
                <div class="flex items-center gap-3">
                    <button onclick="randomFill()" class="text-xs bg-zinc-800 hover:bg-zinc-700 px-4 py-1.5 rounded-xl flex items-center gap-1 btn">🎲 一键随机</button>
                    <button onclick="closeModal()" class="text-3xl leading-none text-zinc-400 hover:text-white">✕</button>
                </div>
            </div>
            <form id="form" class="p-6 space-y-6 max-h-[68vh] overflow-y-auto custom-scroll">
                <input type="hidden" id="editId">
                <div><label class="block text-xs text-zinc-400 mb-1.5">环境名称</label><input id="pName" type="text" required class="w-full bg-zinc-800 border border-zinc-700 focus:border-blue-500 rounded-xl px-4 py-3 text-sm outline-none"></div>
                <div class="grid grid-cols-2 gap-4">
                    <div><label class="block text-xs text-zinc-400 mb-1.5">指纹种子</label><input id="pSeed" type="text" class="w-full bg-zinc-800 border border-zinc-700 focus:border-blue-500 rounded-xl px-4 py-3 text-sm outline-none"></div>
                    <div><label class="block text-xs text-zinc-400 mb-1.5">平台</label><select id="pPlatform" class="w-full bg-zinc-800 border border-zinc-700 focus:border-blue-500 rounded-xl px-4 py-3 text-sm outline-none"><option value="windows">Windows</option><option value="macos">macOS</option><option value="linux">Linux</option></select></div>
                </div>
                <div><label class="block text-xs text-zinc-400 mb-1.5">User-Agent（留空自动）</label><input id="pUa" type="text" class="w-full bg-zinc-800 border border-zinc-700 focus:border-blue-500 rounded-xl px-4 py-3 text-sm outline-none"></div>
                <div class="grid grid-cols-2 gap-4">
                    <div><label class="block text-xs text-zinc-400 mb-1.5">时区</label><input id="pTimezone" type="text" value="Asia/Shanghai" class="w-full bg-zinc-800 border border-zinc-700 focus:border-blue-500 rounded-xl px-4 py-3 text-sm outline-none"></div>
                    <div><label class="block text-xs text-zinc-400 mb-1.5">语言</label><input id="pLang" type="text" value="zh-CN" class="w-full bg-zinc-800 border border-zinc-700 focus:border-blue-500 rounded-xl px-4 py-3 text-sm outline-none"></div>
                </div>
                <details class="group">
                    <summary class="flex items-center justify-between cursor-pointer text-sm text-zinc-400 hover:text-white py-1"><span>硬件与网络设置</span><span class="text-xl transition-transform group-open:rotate-180">›</span></summary>
                    <div class="mt-5 space-y-6 pt-4 border-t border-zinc-700">
                        <div><div class="text-xs text-zinc-500 mb-3">硬件伪装</div>
                            <div class="grid grid-cols-2 gap-4">
                                <div><label class="block text-xs text-zinc-400 mb-1">GPU Vendor</label><input id="pGpuV" type="text" class="w-full bg-zinc-800 border border-zinc-700 focus:border-blue-500 rounded-xl px-4 py-3 text-sm outline-none"></div>
                                <div><label class="block text-xs text-zinc-400 mb-1">GPU Renderer</label><input id="pGpuR" type="text" class="w-full bg-zinc-800 border border-zinc-700 focus:border-blue-500 rounded-xl px-4 py-3 text-sm outline-none"></div>
                            </div>
                            <div class="grid grid-cols-2 gap-4 mt-4">
                                <div><label class="block text-xs text-zinc-400 mb-1">CPU核心数</label><input id="pCpu" type="number" class="w-full bg-zinc-800 border border-zinc-700 focus:border-blue-500 rounded-xl px-4 py-3 text-sm outline-none"></div>
                                <div><label class="block text-xs text-zinc-400 mb-1">内存 (GB)</label><input id="pMem" type="number" class="w-full bg-zinc-800 border border-zinc-700 focus:border-blue-500 rounded-xl px-4 py-3 text-sm outline-none"></div>
                            </div>
                        </div>
                        <div><div class="text-xs text-zinc-500 mb-3">网络与位置</div>
                            <div><label class="block text-xs text-zinc-400 mb-1">代理服务器</label><input id="pProxy" type="text" placeholder="http://..." class="w-full bg-zinc-800 border border-zinc-700 focus:border-blue-500 rounded-xl px-4 py-3 text-sm outline-none"></div>
                            <div class="grid grid-cols-2 gap-4 mt-4">
                                <div><label class="block text-xs text-zinc-400 mb-1">纬度</label><input id="pLat" type="text" class="w-full bg-zinc-800 border border-zinc-700 focus:border-blue-500 rounded-xl px-4 py-3 text-sm outline-none"></div>
                                <div><label class="block text-xs text-zinc-400 mb-1">经度</label><input id="pLon" type="text" class="w-full bg-zinc-800 border border-zinc-700 focus:border-blue-500 rounded-xl px-4 py-3 text-sm outline-none"></div>
                            </div>
                        </div>
                    </div>
                </details>
                <div class="flex gap-3 pt-4">
                    <button type="button" onclick="closeModal()" class="flex-1 py-3 text-sm font-medium border border-zinc-700 hover:bg-zinc-800 rounded-xl btn">取消</button>
                    <button type="submit" class="flex-1 py-3 text-sm font-medium bg-blue-600 hover:bg-blue-500 rounded-xl btn">保存</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        let profiles = [];

        function showToast(msg, success = true) {
            const t = document.getElementById('toast');
            t.innerHTML = `<span class="${success ? 'text-emerald-400' : 'text-red-400'} text-xl">•</span><span class="ml-2">${msg}</span>`;
            t.classList.remove('hidden');
            setTimeout(() => t.classList.add('hidden'), 2000);
        }

        function randomFill() {
            document.getElementById('pSeed').value = Math.random().toString(36).substring(2, 10).toUpperCase();
            const gpus = [{v:"NVIDIA Corporation",r:"NVIDIA GeForce RTX 4060"},{v:"NVIDIA Corporation",r:"NVIDIA GeForce RTX 3070"},{v:"Intel Corporation",r:"Intel(R) UHD Graphics 770"}];
            const gpu = gpus[Math.floor(Math.random()*gpus.length)];
            document.getElementById('pGpuV').value = gpu.v; document.getElementById('pGpuR').value = gpu.r;
            document.getElementById('pCpu').value = [6,8,12,16][Math.floor(Math.random()*4)];
            document.getElementById('pMem').value = [8,16,24,32][Math.floor(Math.random()*4)];
            document.getElementById('pLat').value = (20 + Math.random()*30).toFixed(4);
            document.getElementById('pLon').value = (75 + Math.random()*55).toFixed(4);
        }

        async function load() {
            profiles = await pywebview.api.get_profiles();
            render();
        }

        function filter() { render(); }

        function render() {
            const term = document.getElementById('search').value.toLowerCase();
            const filtered = profiles.filter(p => p.name.toLowerCase().includes(term) || p.id.toLowerCase().includes(term));
            const html = filtered.map(p => {
                const run = p.status === 'running';
                return `<div class="card bg-zinc-900 border border-zinc-800 rounded-2xl p-5 flex flex-col">
                    <div class="flex justify-between items-start">
                        <div><div class="font-medium text-base">${p.name}</div><div class="text-[10px] text-zinc-500 font-mono mt-0.5">ID: ${p.id}</div></div>
                        <div class="flex items-center gap-1.5 text-xs ${run ? 'text-emerald-400' : 'text-zinc-500'}">
                            <div class="w-2 h-2 rounded-full ${run ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-600'}"></div>
                            ${run ? '运行中' : '已停止'}
                        </div>
                    </div>
                    <div class="flex-1 text-xs text-zinc-400 mt-5 space-y-0.5">
                        <div>平台: ${p.config.platform || '自动'}</div>
                        <div>创建: ${p.created_at}</div>
                    </div>
                    <div class="flex gap-2 mt-6">
                        ${run ? `<button onclick="stop('${p.id}')" class="flex-1 bg-orange-600/90 hover:bg-orange-600 py-2.5 rounded-xl text-sm btn">停止</button>` : `<button onclick="start('${p.id}')" class="flex-1 bg-emerald-600 hover:bg-emerald-500 py-2.5 rounded-xl text-sm btn">启动</button>`}
                        <button onclick="edit('${p.id}')" class="flex-1 bg-zinc-800 hover:bg-zinc-700 py-2.5 rounded-xl text-sm btn">编辑</button>
                        <button onclick="del('${p.id}')" class="w-9 h-9 flex items-center justify-center text-red-400 hover:bg-zinc-800 rounded-xl btn">🗑</button>
                    </div>
                </div>`;
            }).join('');
            document.getElementById('grid').innerHTML = html || `<div class="col-span-3 py-20 text-center text-zinc-500">暂无环境，点击上方新建</div>`;
        }

        function openModal(id = null) {
            document.getElementById('modal').classList.remove('hidden');
            document.getElementById('form').reset();
            document.getElementById('editId').value = '';
            document.getElementById('modalTitle').textContent = id ? '编辑环境' : '新建环境';
            if (id) {
                const p = profiles.find(x => x.id === id);
                if (p) {
                    document.getElementById('editId').value = p.id;
                    document.getElementById('pName').value = p.name;
                    const c = p.config || {};
                    document.getElementById('pSeed').value = c.fingerprint_seed || '';
                    document.getElementById('pPlatform').value = c.platform || 'windows';
                    document.getElementById('pUa').value = c.ua || '';
                    document.getElementById('pTimezone').value = c.timezone || 'Asia/Shanghai';
                    document.getElementById('pLang').value = c.language || 'zh-CN';
                    document.getElementById('pGpuV').value = c.gpu_vendor || '';
                    document.getElementById('pGpuR').value = c.gpu_renderer || '';
                    document.getElementById('pCpu').value = c.cpu_cores || '';
                    document.getElementById('pMem').value = c.memory_size || '';
                    document.getElementById('pProxy').value = c.proxy || '';
                    document.getElementById('pLat').value = c.geo_lat || '';
                    document.getElementById('pLon').value = c.geo_lon || '';
                }
            } else {
                randomFill();
            }
        }

        function closeModal() { document.getElementById('modal').classList.add('hidden'); }

        document.getElementById('form').onsubmit = async e => {
            e.preventDefault();
            const editId = document.getElementById('editId').value;
            const name = document.getElementById('pName').value.trim();
            const config = {fingerprint_seed: document.getElementById('pSeed').value, platform: document.getElementById('pPlatform').value, ua: document.getElementById('pUa').value, timezone: document.getElementById('pTimezone').value, language: document.getElementById('pLang').value, gpu_vendor: document.getElementById('pGpuV').value, gpu_renderer: document.getElementById('pGpuR').value, cpu_cores: document.getElementById('pCpu').value, memory_size: document.getElementById('pMem').value, proxy: document.getElementById('pProxy').value, geo_lat: document.getElementById('pLat').value, geo_lon: document.getElementById('pLon').value, brand: "Chrome"};
            if (editId) {
                await pywebview.api.update_profile(editId, name, JSON.stringify(config));
                showToast('更新成功');
            } else {
                await pywebview.api.create_profile(name, JSON.stringify(config));
                showToast('创建成功');
            }
            closeModal();
            load();
        };

        async function start(id) { 
            const r = await pywebview.api.start_profile(id);
            showToast(r.message, r.success);
            if (r.success) load();
        }

        async function stop(id) { 
            await pywebview.api.stop_profile(id);
            showToast('已停止');
            load();
        }

        async function del(id) {
            if (confirm('确定删除此环境？所有本地数据将被永久清除')) {
                await pywebview.api.delete_profile(id);
                showToast('已删除');
                load();
            }
        }

        function edit(id) { openModal(id); }

        window.addEventListener('pywebviewready', () => {
            load();
            setInterval(load, 1500);   // 1.5秒刷新，速度快且不卡
        });
    </script>
</body>
</html>
"""

# ================= 主程序 =================


def main():
    if os.name == 'nt':
        try:
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 6)  # 最小化CMD窗口
        except:
            pass

    if not os.path.exists(CHROME_PATH):
        print(f"错误: 未找到 Chromium: {CHROME_PATH}")
        input("按回车退出...")
        return

    window = webview.create_window(
        title='指纹浏览器管理器',
        html=HTML_CONTENT,
        js_api=api,
        width=1050,
        height=720,
        min_size=(900, 600),
        background_color='#18181b'
    )
    webview.start(debug=False)

if __name__ == '__main__':
    main()