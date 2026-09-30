import flet as ft
import os
import shutil
import time
import threading
import requests
from requests.adapters import HTTPAdapter
import traceback
from datetime import datetime
from urllib.parse import unquote

# 📁 ဖိုင်သိမ်းဆည်းမည့် လမ်းကြောင်း
DOWNLOAD_DIR = "/storage/emulated/0/Download/DataPlus"

# ⚡ High-Speed Connection Pool (Local Network အတွက် အမြန်ဆုံး စနစ်)
http_session = requests.Session()
adapter = HTTPAdapter(pool_connections=16, pool_maxsize=16, max_retries=2)
http_session.mount("http://", adapter)
http_session.mount("https://", adapter)

# 💾 ဖုန်း STORAGE လက်ကျန် တွက်ချက်သည့် Helper
def get_phone_storage_info():
    paths_to_check = ["/storage/emulated/0", DOWNLOAD_DIR, os.path.expanduser("~"), "."]
    for path in paths_to_check:
        try:
            total, used, free = shutil.disk_usage(path)
            free_gb = free / (1024 ** 3)
            total_gb = total / (1024 ** 3)
            free_pct = (free / total * 100) if total > 0 else 0
            used_ratio = used / total if total > 0 else 0.0
            return free_gb, total_gb, free_pct, used_ratio
        except Exception:
            continue
    return 0.0, 0.0, 0.0, 0.0

# 📋 Clipboard Helper Functions
def get_clipboard_text(page: ft.Page) -> str:
    try:
        if hasattr(page, "get_clipboard"):
            return page.get_clipboard() or ""
        elif hasattr(page, "clipboard") and hasattr(page.clipboard, "get"):
            return page.clipboard.get() or ""
    except Exception:
        pass
    return ""

def set_clipboard_text(page: ft.Page, text: str):
    try:
        if hasattr(page, "set_clipboard"):
            page.set_clipboard(text)
        elif hasattr(page, "clipboard") and hasattr(page.clipboard, "set"):
            page.clipboard.set(text)
    except Exception:
        pass

# 🚨 Error Dialog နှင့် Copy စနစ်
def show_error_dialog(page: ft.Page, error_text: str):
    def copy_error_to_clipboard(_):
        set_clipboard_text(page, error_text)
        page.snack_bar = ft.SnackBar(
            content=ft.Text("✅ Error ကို Clipboard သို့ Copy ကူးပြီးပါပြီ!"),
            bgcolor="#238636"
        )
        page.snack_bar.open = True
        page.update()

    err_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.ERROR_OUTLINE, color="#F85149", size=24),
                ft.Text("App Error", color="#F85149", weight=ft.FontWeight.BOLD, size=16),
            ]
        ),
        content=ft.Container(
            bgcolor="#0D1117",
            border=ft.border.all(1, "#30363D"),
            border_radius=8,
            padding=10,
            content=ft.Text(error_text, size=11, color="#FFA07A", selectable=True, font_family="monospace"),
            max_height=200,
        ),
        actions=[
            ft.ElevatedButton("📋 Copy Error", bgcolor="#0275D8", color="white", on_click=copy_error_to_clipboard),
            ft.TextButton("Close", on_click=lambda _: setattr(err_dialog, "open", False) or page.update())
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.dialog = err_dialog
    err_dialog.open = True
    page.update()


class ADMDownloaderApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "DATA PLUS Downloader"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = "#101317"
        self.page.padding = 0

        self.current_tab = "Finished"
        self.downloads = []
        self.is_downloading = False

        try:
            if not os.path.exists(DOWNLOAD_DIR):
                os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        except Exception:
            pass

        self.setup_ui()
        self.refresh_list()  # ✅ စတင်ချိန်တွင် စာရင်းကို အလိုအလျောက် ပေါ်စေရန်
        self.check_clipboard_and_start()

    def show_error(self, err_msg: str):
        show_error_dialog(self.page, err_msg)

    def setup_ui(self):
        # 🔝 ၁။ Top Bar
        self.title_text = ft.Text(self.current_tab, size=18, weight=ft.FontWeight.BOLD, color="white")
        self.top_actions_row = ft.Row(spacing=4, controls=[])

        self.top_bar = ft.Container(
            bgcolor="#1E232B",
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.MENU, color="#C9D1D9", size=24),
                            ft.Container(width=10),
                            self.title_text,
                        ]
                    ),
                    self.top_actions_row
                ]
            )
        )

        # 💾 ၂။ "ဖုန်း STORAGE လက်ကျန်" ထင်ရှားသော Card (စိမ်းပြာရောင် စာလုံးကြီးများ)
        free_gb, total_gb, free_pct, used_ratio = get_phone_storage_info()
        
        self.storage_free_text = ft.Text(f"လက်ကျန်: {free_gb:.1f} GB", size=16, color="#00E676", weight=ft.FontWeight.BOLD)
        self.storage_total_text = ft.Text(f"(စုစုပေါင်း: {total_gb:.1f} GB)", size=12, color="#8B949E", weight=ft.FontWeight.W_500)
        self.storage_badge = ft.Text(f"{free_pct:.0f}% ကျန်ရှိ", size=11, color="white", weight=ft.FontWeight.BOLD)
        
        self.storage_progress = ft.ProgressBar(
            value=used_ratio,
            color="#00E676",
            bgcolor="#263342",
            height=8,
            border_radius=4,
        )

        self.storage_card = ft.Container(
            margin=ft.margin.symmetric(horizontal=10, vertical=6),
            padding=ft.padding.symmetric(horizontal=14, vertical=10),
            bgcolor="#16222F",
            border=ft.border.all(1.5, "#2563EB"),
            border_radius=10,
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=6,
                                controls=[
                                    ft.Icon(ft.Icons.SD_STORAGE, size=18, color="#00E676"),
                                    ft.Text("ဖုန်း STORAGE လက်ကျန်", size=13, color="#FFFFFF", weight=ft.FontWeight.BOLD),
                                ]
                            ),
                            ft.Container(
                                bgcolor="#1E40AF",
                                border_radius=6,
                                padding=ft.padding.symmetric(horizontal=8, vertical=2),
                                content=self.storage_badge
                            )
                        ]
                    ),
                    # ✅ Safe Alignment (Error လုံးဝမတက်စေရန် CENTER သုံးထားသည်)
                    ft.Row(
                        spacing=8,
                        alignment=ft.MainAxisAlignment.START,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            self.storage_free_text,
                            self.storage_total_text,
                        ]
                    ),
                    self.storage_progress,
                ]
            )
        )

        # 📋 ၃။ Download Items List
        self.list_view = ft.ListView(
            expand=True,
            spacing=0,
            padding=ft.padding.all(0)
        )

        # 🔻 ၄။ Bottom Navigation Bar
        self.queue_icon = ft.Icon(ft.Icons.ACCESS_TIME, color="#8B949E", size=20)
        self.queue_text = ft.Text("Queue", size=11, color="#8B949E")
        
        self.finished_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, color="#00E676", size=20)
        self.finished_text = ft.Text("Finished", size=11, color="#00E676")

        self.bottom_bar = ft.Container(
            bgcolor="#1E232B",
            padding=ft.padding.symmetric(vertical=6, horizontal=15),
            border=ft.border.only(top=ft.BorderSide(0.5, "#30363D")),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.POWER_SETTINGS_NEW,
                        icon_color="#F85149",
                        icon_size=22,
                        tooltip="Exit App",
                        on_click=lambda _: self.page.window.close() if hasattr(self.page, "window") else None
                    ),
                    ft.Container(
                        content=ft.Icon(ft.Icons.ADD, color="white", size=24),
                        bgcolor="#238636",
                        border_radius=22,
                        padding=ft.padding.all(7),
                        ink=True,
                        tooltip="Add Links",
                        on_click=lambda _: self.show_add_links_dialog()
                    ),
                    ft.Container(
                        content=ft.Column(
                            alignment=ft.MainAxisAlignment.CENTER,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=1,
                            controls=[self.queue_icon, self.queue_text]
                        ),
                        ink=True,
                        border_radius=8,
                        padding=ft.padding.symmetric(horizontal=12, vertical=4),
                        on_click=lambda _: self.switch_tab("Queue")
                    ),
                    ft.Container(
                        content=ft.Column(
                            alignment=ft.MainAxisAlignment.CENTER,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=1,
                            controls=[self.finished_icon, self.finished_text]
                        ),
                        ink=True,
                        border_radius=8,
                        padding=ft.padding.symmetric(horizontal=12, vertical=4),
                        on_click=lambda _: self.switch_tab("Finished")
                    ),
                ]
            )
        )

        self.page.add(
            ft.Column(
                expand=True,
                spacing=0,
                controls=[
                    self.top_bar,
                    self.storage_card,
                    self.list_view,
                    self.bottom_bar
                ]
            )
        )

    def update_top_actions(self):
        tab = self.current_tab
        current_items = [
            it for it in self.downloads 
            if (tab == "Finished" and it["status"] == "finished") or
               (tab == "Queue" and it["status"] != "finished")
        ]
        selected_items = [it for it in current_items if it.get("selected", False)]
        self.top_actions_row.controls.clear()

        if current_items:
            all_selected = len(selected_items) == len(current_items) and len(current_items) > 0
            self.top_actions_row.controls.append(
                ft.TextButton(
                    "All" if not all_selected else "None",
                    icon=ft.Icons.SELECT_ALL,
                    style=ft.ButtonStyle(color="#58A6FF", padding=ft.padding.all(4)),
                    on_click=lambda _: self.toggle_select_all(not all_selected)
                )
            )

            if selected_items:
                self.top_actions_row.controls.append(
                    ft.ElevatedButton(
                        f"Delete ({len(selected_items)})",
                        bgcolor="#B91C1C",
                        color="white",
                        style=ft.ButtonStyle(padding=ft.padding.symmetric(horizontal=8, vertical=4)),
                        on_click=lambda _: self.delete_selected_items(selected_items)
                    )
                )
            else:
                self.top_actions_row.controls.append(
                    ft.TextButton(
                        "Remove All",
                        icon=ft.Icons.DELETE_SWEEP,
                        icon_color="#F85149",
                        style=ft.ButtonStyle(color="#F85149", padding=ft.padding.all(4)),
                        on_click=lambda _: self.confirm_remove_all()
                    )
                )
        self.page.update()

    def toggle_select_all(self, select_value):
        tab = self.current_tab
        for it in self.downloads:
            if (tab == "Finished" and it["status"] == "finished") or (tab == "Queue" and it["status"] != "finished"):
                it["selected"] = select_value
        self.refresh_list()

    def delete_selected_items(self, items):
        for it in items:
            self.clean_and_remove_item(it)
        self.refresh_list()
        self.update_storage_display()

    def toggle_pause_resume(self, item):
        if item["status"] == "downloading":
            item["pause_requested"] = True
            item["status"] = "paused"
            item["speed"] = "Paused"
            self.refresh_list()
        elif item["status"] == "paused":
            item["pause_requested"] = False
            item["status"] = "queued"
            item["speed"] = "Resuming..."
            self.refresh_list()
            if not self.is_downloading:
                threading.Thread(target=self.start_download_worker, daemon=True).start()

    def clean_and_remove_item(self, item):
        item["cancel_requested"] = True
        item["pause_requested"] = True
        filepath = os.path.join(DOWNLOAD_DIR, item["name"])
        tmp_file = f"{filepath}.tmp"
        if os.path.exists(tmp_file):
            try: os.remove(tmp_file)
            except Exception: pass
        if item in self.downloads:
            self.downloads.remove(item)

    def delete_single_item(self, item):
        self.clean_and_remove_item(item)
        self.refresh_list()
        self.update_storage_display()

    def confirm_remove_all(self):
        tab = self.current_tab
        items_to_remove = [
            it for it in self.downloads 
            if (tab == "Finished" and it["status"] == "finished") or
               (tab == "Queue" and it["status"] != "finished")
        ]
        if not items_to_remove: return

        def do_remove_all(_):
            for it in items_to_remove:
                self.clean_and_remove_item(it)
            dialog.open = False
            self.refresh_list()
            self.update_storage_display()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Remove All ({tab})", color="#F85149", weight=ft.FontWeight.BOLD),
            content=ft.Text(f"{tab} စာရင်းထဲရှိ ဖိုင်အားလုံးကို ဖျက်ပစ်ရန် သေချာပါသလား?"),
            actions=[
                ft.TextButton("မလုပ်တော့ပါ", on_click=lambda _: setattr(dialog, "open", False) or self.page.update()),
                ft.ElevatedButton("ဖျက်မည်", bgcolor="#F85149", color="white", on_click=do_remove_all),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    # 🎨 ADM Style Item Card (စာတန်းကို Progress Bar အပေါ် အလယ်တွင် ထားရှိထားသည်)
    def build_adm_card(self, item):
        is_done = item["status"] == "finished"
        is_downloading = item["status"] == "downloading"
        is_paused = item["status"] == "paused"
        progress = item["progress"]

        if is_done:
            status_btn = ft.Icon(ft.Icons.CHECK_CIRCLE, color="#00E676", size=18)
        elif is_downloading:
            status_btn = ft.IconButton(
                icon=ft.Icons.PAUSE_CIRCLE_FILLED,
                icon_color="#E3B341",
                icon_size=20,
                tooltip="ခေတ္တရပ်မည်",
                on_click=lambda _, it=item: self.toggle_pause_resume(it)
            )
        elif is_paused:
            status_btn = ft.IconButton(
                icon=ft.Icons.PLAY_CIRCLE_FILL,
                icon_color="#58A6FF",
                icon_size=20,
                tooltip="ဆက်လက်ဒေါင်းမည်",
                on_click=lambda _, it=item: self.toggle_pause_resume(it)
            )
        else:
            status_btn = ft.Icon(ft.Icons.ACCESS_TIME, color="#8B949E", size=18)

        center_speed_text = f"{item['speed']}  •  {item['eta']}"
        center_color = "#00E676" if is_downloading else ("#E3B341" if is_paused else "#76B82A")
        if is_done:
            center_speed_text = "COMPLETE ✅"
            center_color = "#00E676"

        return ft.Container(
            bgcolor="#13171D",
            padding=ft.padding.symmetric(horizontal=10, vertical=7),
            border=ft.border.only(bottom=ft.BorderSide(0.6, "#21262E")),
            content=ft.Column(
                spacing=4,
                controls=[
                    # ၁။ ဖိုင်အမည်နှင့် Checkbox အတန်း (Text Overflow မဖြစ်စေရန် Container ဖြင့် ထိန်းထားသည်)
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                expand=True,
                                controls=[
                                    ft.Checkbox(
                                        value=item.get("selected", False),
                                        fill_color="#2563EB",
                                        check_color="white",
                                        on_change=lambda e, it=item: self.on_item_select_changed(it, e.control.value)
                                    ),
                                    status_btn,
                                    ft.Container(
                                        expand=True,
                                        content=ft.Text(
                                            item["name"],
                                            size=13,
                                            color="white",
                                            weight=ft.FontWeight.W_500,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                            max_lines=1
                                        )
                                    )
                                ]
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_color="#8B949E",
                                icon_size=18,
                                tooltip="ဖျက်မည်",
                                on_click=lambda _, it=item: self.delete_single_item(it)
                            )
                        ]
                    ),

                    # ၂။ 🌟 အပေါ်တန်း အလယ်ရှိ ထင်ရှားသော Speed စာတန်း
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(item['size'], size=11, color="#8B949E", weight=ft.FontWeight.W_500),
                            ft.Text(center_speed_text, size=12, color=center_color, weight=ft.FontWeight.BOLD),
                            ft.Text(item["date"], size=10.5, color="#8B949E")
                        ]
                    ),

                    # ၃။ 🟩 သီးသန့် အစိမ်းရောင် Progress Bar
                    ft.ProgressBar(
                        value=progress,
                        color="#E3B341" if is_paused else "#00E676",
                        bgcolor="#21262E",
                        height=6,
                        border_radius=3,
                    )
                ]
            )
        )

    def on_item_select_changed(self, item, value):
        item["selected"] = value
        self.update_top_actions()

    def refresh_list(self):
        self.list_view.controls.clear()
        filtered = [
            it for it in self.downloads 
            if (self.current_tab == "Finished" and it["status"] == "finished") or
               (self.current_tab == "Queue" and it["status"] != "finished")
        ]

        if not filtered:
            self.list_view.controls.append(
                ft.Container(
                    alignment=ft.alignment.center,
                    padding=ft.padding.only(top=80),
                    content=ft.Text(f"No {self.current_tab} downloads", color="#484F58", size=14)
                )
            )
        else:
            for item in filtered:
                self.list_view.controls.append(self.build_adm_card(item))

        self.update_top_actions()
        self.page.update()

    def update_storage_display(self):
        free_gb, total_gb, free_pct, used_ratio = get_phone_storage_info()
        self.storage_free_text.value = f"လက်ကျန်: {free_gb:.1f} GB"
        self.storage_total_text.value = f"(စုစုပေါင်း: {total_gb:.1f} GB)"
        self.storage_badge.value = f"{free_pct:.0f}% ကျန်ရှိ"
        self.storage_progress.value = used_ratio
        self.page.update()

    def switch_tab(self, tab_name):
        self.current_tab = tab_name
        self.title_text.value = tab_name

        if tab_name == "Queue":
            self.queue_icon.color = "#58A6FF"
            self.queue_text.color = "#58A6FF"
            self.finished_icon.color = "#8B949E"
            self.finished_text.color = "#8B949E"
        else:
            self.queue_icon.color = "#8B949E"
            self.queue_text.color = "#8B949E"
            self.finished_icon.color = "#00E676"
            self.finished_text.color = "#00E676"

        self.refresh_list()

    def show_add_links_dialog(self):
        text_field = ft.TextField(
            multiline=True,
            min_lines=4,
            max_lines=8,
            hint_text="ဒီနေရာတွင် Link များကို ကူးထည့်ပါ (တစ်ကြောင်းလျှင် Link တစ်ခု)...",
            border_color="#30363D",
            focused_border_color="#238636",
            bgcolor="#0D1117",
            text_size=12,
        )

        def paste_from_clipboard(_):
            clip = get_clipboard_text(self.page)
            if clip:
                text_field.value = clip
                self.page.update()

        def confirm_add(_):
            raw_text = text_field.value or ""
            urls = [u.strip() for u in raw_text.split("\n") if u.strip().startswith("http")]
            dialog.open = False
            self.page.update()
            if urls:
                self.add_urls_and_start(urls)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ADD_LINK, color="#238636", size=22),
                    ft.Text("Add Download Links", size=16, weight=ft.FontWeight.BOLD, color="white"),
                ]
            ),
            content=ft.Container(
                width=350,
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text("ဒေါင်းလုဒ် Link များ ထည့်သွင်းပါ:", size=12, color="#8B949E"),
                                ft.TextButton("📋 Paste", icon=ft.Icons.CONTENT_PASTE, on_click=paste_from_clipboard)
                            ]
                        ),
                        text_field,
                    ]
                )
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: setattr(dialog, "open", False) or self.page.update()),
                ft.ElevatedButton("🚀 စတင်ဒေါင်းမည်", bgcolor="#238636", color="white", on_click=confirm_add)
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def add_urls_and_start(self, urls):
        added = False
        for url in urls:
            if not any(d["url"] == url for d in self.downloads):
                filename = unquote(url.split("/")[-1].split("?")[0]) or f"file_{int(time.time())}.mp4"
                self.downloads.append({
                    "url": url,
                    "name": filename,
                    "status": "queued",
                    "progress": 0.0,
                    "size": "0M",
                    "speed": "0.0mb/s",
                    "eta": "--:--",
                    "date": datetime.now().strftime("%b %d, %Y %I:%M:%S %p"),
                    "pause_requested": False,
                    "cancel_requested": False,
                    "selected": False
                })
                added = True
        if added:
            self.switch_tab("Queue")
            if not self.is_downloading:
                threading.Thread(target=self.start_download_worker, daemon=True).start()

    def check_clipboard_and_start(self):
        def _read_clip():
            try:
                time.sleep(0.3)
                clip_text = get_clipboard_text(self.page)
                if clip_text and "http" in clip_text:
                    urls = [u.strip() for u in clip_text.split("\n") if u.strip().startswith("http")]
                    if urls:
                        self.add_urls_and_start(urls)
            except Exception as e:
                print("Clipboard check error:", e)

        threading.Thread(target=_read_clip, daemon=True).start()

    # 🚀 Multi-thread 4 with Direct-Seek (Zero Merge Time & High-Speed)
    def download_file_direct_seek_4(self, item, filepath):
        tmp_filepath = f"{filepath}.tmp"
        
        head_resp = http_session.head(item["url"], timeout=10, allow_redirects=True)
        total_len = int(head_resp.headers.get("content-length", 0))

        can_range = False
        if total_len > 2 * 1024 * 1024:
            try:
                test_resp = http_session.get(item["url"], headers={"Range": "bytes=0-0"}, timeout=6)
                if test_resp.status_code == 206:
                    can_range = True
            except Exception:
                pass

        CHUNK_SIZE = 1024 * 512  # 512KB Buffer

        # ၁။ Range ထောက်ပံ့ပါက Multi-thread 4 Direct Seek ဖြင့် ဒေါင်းခြင်း
        if can_range and total_len > 0:
            if not os.path.exists(tmp_filepath) or os.path.getsize(tmp_filepath) != total_len:
                try:
                    with open(tmp_filepath, "wb") as f:
                        f.truncate(total_len)
                except Exception:
                    with open(tmp_filepath, "wb") as f:
                        f.seek(total_len - 1)
                        f.write(b"\0")

            NUM_THREADS = 4
            part_size = total_len // NUM_THREADS
            parts = []
            for i in range(NUM_THREADS):
                s = i * part_size
                e = (s + part_size - 1) if i < NUM_THREADS - 1 else (total_len - 1)
                parts.append((i, s, e))

            bytes_downloaded = [0] * NUM_THREADS
            progress_lock = threading.Lock()

            def thread_worker(idx, p_start, p_end):
                req_headers = {"Range": f"bytes={p_start}-{p_end}", "User-Agent": "Mozilla/5.0"}
                with http_session.get(item["url"], headers=req_headers, stream=True, timeout=20) as resp:
                    resp.raise_for_status()
                    with open(tmp_filepath, "r+b") as out_f:
                        out_f.seek(p_start)
                        for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                            if item.get("pause_requested") or item.get("cancel_requested"):
                                break
                            if chunk:
                                out_f.write(chunk)
                                with progress_lock:
                                    bytes_downloaded[idx] += len(chunk)

            workers = [threading.Thread(target=thread_worker, args=p, daemon=True) for p in parts]
            for w in workers: w.start()

            start_time = time.time()
            last_time = start_time
            last_bytes = 0

            while any(w.is_alive() for w in workers):
                if item.get("pause_requested") or item.get("cancel_requested"):
                    break
                time.sleep(0.4)
                now = time.time()
                if now - last_time >= 0.8:
                    with progress_lock:
                        curr_bytes = sum(bytes_downloaded)
                    speed_mb = (curr_bytes - last_bytes) / (now - last_time) / (1024 * 1024)
                    last_time = now
                    last_bytes = curr_bytes

                    item["progress"] = min(curr_bytes / total_len, 0.99)
                    item["size"] = f"{int(total_len / (1024 * 1024))}m"
                    rem_sec = int((total_len - curr_bytes) / (speed_mb * 1024 * 1024)) if speed_mb > 0 else 0
                    item["eta"] = f"{rem_sec // 60:02d}:{rem_sec % 60:02d}"
                    item["speed"] = f"{speed_mb:.1f}mb/s"
                    self.refresh_list()

            for w in workers: w.join(timeout=0.3)

            if item.get("cancel_requested"): return "cancelled"
            if item.get("pause_requested"): return "paused"

            with progress_lock:
                total_dl = sum(bytes_downloaded)
            if total_dl >= total_len:
                if os.path.exists(filepath):
                    try: os.remove(filepath)
                    except Exception: pass
                os.rename(tmp_filepath, filepath)
                return "finished"
            return "incomplete"

        # ၂။ Single Stream Fallback
        else:
            with http_session.get(item["url"], stream=True, timeout=20) as resp:
                if total_len == 0:
                    total_len = int(resp.headers.get("content-length", 0))
                downloaded = 0
                start_time = time.time()
                last_time = start_time
                last_bytes = 0

                with open(tmp_filepath, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                        if item.get("pause_requested") or item.get("cancel_requested"):
                            break
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            now = time.time()
                            if now - last_time >= 0.8:
                                speed_mb = (downloaded - last_bytes) / (now - last_time) / (1024 * 1024)
                                last_time = now
                                last_bytes = downloaded
                                if total_len > 0:
                                    item["progress"] = min(downloaded / total_len, 0.99)
                                    item["size"] = f"{int(total_len / (1024 * 1024))}m"
                                    rem_sec = int((total_len - downloaded) / (speed_mb * 1024 * 1024)) if speed_mb > 0 else 0
                                    item["eta"] = f"{rem_sec // 60:02d}:{rem_sec % 60:02d}"
                                item["speed"] = f"{speed_mb:.1f}mb/s"
                                self.refresh_list()

            if item.get("cancel_requested"): return "cancelled"
            if item.get("pause_requested"): return "paused"

            if os.path.exists(tmp_filepath):
                if os.path.exists(filepath):
                    try: os.remove(filepath)
                    except Exception: pass
                os.rename(tmp_filepath, filepath)
            return "finished"

    # 🚀 Download Worker Loop
    def start_download_worker(self):
        try:
            self.is_downloading = True
            while True:
                queued = [d for d in self.downloads if d["status"] == "queued"]
                if not queued:
                    break

                item = queued[0]
                item["status"] = "downloading"
                item["pause_requested"] = False
                item["cancel_requested"] = False
                self.refresh_list()

                filepath = os.path.join(DOWNLOAD_DIR, item["name"])
                try:
                    result = self.download_file_direct_seek_4(item, filepath)
                    if result == "finished":
                        item["status"] = "finished"
                        item["progress"] = 1.0
                        item["speed"] = "Done"
                        item["eta"] = "00:00"
                        item["date"] = datetime.now().strftime("%b %d, %Y %I:%M:%S %p")
                        self.update_storage_display()
                    elif result == "paused":
                        item["status"] = "paused"
                    elif result == "cancelled":
                        continue
                    else:
                        item["status"] = "error"
                except Exception as e:
                    item["status"] = "error"
                    print("Download item error:", e)

                self.refresh_list()

            self.is_downloading = False
            if not any(d["status"] in ["queued", "downloading"] for d in self.downloads):
                self.switch_tab("Finished")
        except Exception:
            self.is_downloading = False
            err_msg = traceback.format_exc()
            self.show_error(err_msg)


def main(page: ft.Page):
    try:
        ADMDownloaderApp(page)
    except Exception:
        err_msg = traceback.format_exc()
        print("Fatal error in main:", err_msg)
        show_error_dialog(page, err_msg)

if __name__ == "__main__":
    ft.app(target=main)
