import flet as ft
import os
import requests
import threading
import urllib.parse
from pathlib import Path
import time

def main(page: ft.Page):
    page.title = "DATA PLUS Downloader"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.bgcolor = "#0a0a0a"
    page.padding = 20
    page.window_width = 450
    page.window_height = 800

    status_text = ft.Text("📥 ဒေါင်းလုဒ်ဆွဲရန် Link များကို ထည့်ပါ", color="#4a9eff", size=13, weight=ft.FontWeight.BOLD)
    
    links_input = ft.TextField(
        label="Download Links (တစ်ကြောင်းလျှင် တစ်ခု)",
        multiline=True,
        min_lines=3,
        max_lines=5,
        border_color="#4a9eff",
        color="#ffffff",
        label_style=ft.TextStyle(color="#aaaaaa"),
        bgcolor="#1e1e1e"
    )

    download_tasks = {}  
    finished_tasks = {}  
    
    downloading_list = ft.ListView(expand=1, spacing=8, padding=5, auto_scroll=True)
    finished_list = ft.ListView(expand=1, spacing=8, padding=5, auto_scroll=True)

    def paste_from_clipboard(e):
        try:
            clipboard_data = page.get_clipboard()
            if clipboard_data:
                links_input.value = clipboard_data
                links_input.update()
                status_text.value = "📋 Clipboard မှ Link များကို ထည့်ပြီးပါပြီ။"
            else:
                status_text.value = "⚠️ Clipboard တွင် ဘာမှ မရှိပါ။"
            status_text.update()
        except Exception as ex:
            status_text.value = "❌ Paste မရပါ။ (Ctrl+V ကို သုံးပါ)"
            status_text.update()

    def clear_input(e):
        links_input.value = ""
        links_input.update()
        status_text.value = "🗑️ Link အားလုံး ရှင်းလင်းပြီးပါပြီ။"
        status_text.update()

    def clear_finished_list(e):
        finished_tasks.clear()
        update_ui()
        status_text.value = "🧹 Finished စာရင်းများ ရှင်းလင်းပြီးပါပြီ။"
        status_text.update()

    def clear_downloading_list(e):
        for fname in list(download_tasks.keys()):
            download_tasks[fname]['control'] = 'stopped'
        download_tasks.clear()
        update_ui()
        status_text.value = "🧹 Downloading စာရင်းများ အားလုံးရှင်းလင်းပြီးပါပြီ။"
        status_text.update()

    def delete_downloading_task(e):
        fname = e.control.data
        if fname in download_tasks:
            download_tasks[fname]['control'] = 'stopped'
            del download_tasks[fname]
            update_ui()

    def delete_finished_task(e):
        fname = e.control.data
        if fname in finished_tasks:
            del finished_tasks[fname]
            update_ui()

    tab_btn_1 = ft.ElevatedButton(text="📥 Downloading (0)", bgcolor="#222222", color="#4a9eff")
    tab_btn_2 = ft.ElevatedButton(text="✅ Finished (0)", bgcolor="#222222", color="#2ecc71")

    def update_ui():
        try:
            active_count = len(download_tasks)
            finished_count = len(finished_tasks)
            
            tab_btn_1.text = f"📥 Downloading ({active_count})"
            tab_btn_1.update()
            
            tab_btn_2.text = f"✅ Finished ({finished_count})"
            tab_btn_2.update()

            downloading_list.controls.clear()
            for filename, info in download_tasks.items():
                status_color = "#00ff88" if info['status'] == 'Downloading' else ("#e67e22" if info['status'] == 'Paused' else "#ff4444")
                if info['status'] == 'Merging...':
                    status_color = "#f1c40f"
                    
                downloading_list.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Text(filename, size=11, color="#ffffff", weight=ft.FontWeight.BOLD, expand=True),
                                ft.Text(info['speed'], size=10, color="#4a9eff"),
                                ft.Text(f"{info['percent']}%", size=11, color=status_color, weight=ft.FontWeight.BOLD)
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.ProgressBar(value=info['percent']/100, color="#00ff88", bgcolor="#252525", height=6),
                            ft.Row([
                                ft.Text(info['status'], size=9, color=status_color),
                                ft.Row([
                                    ft.ElevatedButton(
                                        text="▶/⏸" if info['status'] != 'Paused' else "▶",
                                        data=filename, on_click=toggle_pause_resume, bgcolor="#333333", color="#ffffff", style=ft.ButtonStyle(padding=2)
                                    ),
                                    ft.ElevatedButton(
                                        text="⏹ Stop",
                                        data=filename, on_click=stop_download_task, bgcolor="#552222", color="#ffffff", style=ft.ButtonStyle(padding=2)
                                    ),
                                    ft.ElevatedButton(
                                        text="🗑️",  # တစ်ဖိုင်ချင်းဖျက်ရန် ခလုတ်
                                        data=filename, on_click=delete_downloading_task, bgcolor="#772222", color="#ffffff", style=ft.ButtonStyle(padding=2)
                                    )
                                ], spacing=4)
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                        ], spacing=4),
                        bgcolor="#161616",
                        padding=10,
                        border_radius=8
                    )
                )

            finished_list.controls.clear()
            for filename, info in finished_tasks.items():
                finished_list.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Text(filename, size=11, color="#2ecc71", weight=ft.FontWeight.BOLD, expand=True),
                                ft.ElevatedButton(
                                    text="🗑️ ဖျက်မည်",
                                    data=filename, on_click=delete_finished_task, bgcolor="#772222", color="#ffffff", style=ft.ButtonStyle(padding=2)
                                )
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Text(f"📂 သိမ်းဆည်းရာ: {info['path']}", size=9, color="#888888")
                        ], spacing=4),
                        bgcolor="#161616",
                        padding=10,
                        border_radius=8
                    )
                )
            page.update()
        except Exception:
            pass

    def toggle_pause_resume(e):
        fname = e.control.data
        if fname in download_tasks:
            if download_tasks[fname]['status'] == 'Paused':
                download_tasks[fname]['status'] = 'Downloading'
                download_tasks[fname]['control'] = 'running'
            else:
                download_tasks[fname]['status'] = 'Paused'
                download_tasks[fname]['control'] = 'paused'
            update_ui()

    def stop_download_task(e):
        fname = e.control.data
        if fname in download_tasks:
            download_tasks[fname]['status'] = 'Stopped'
            download_tasks[fname]['control'] = 'stopped'
            update_ui()

    def start_download(e):
        raw_text = links_input.value.strip()
        if not raw_text:
            status_text.value = "❌ ကျေးဇူးပြု၍ Link ထည့်ပါ။"
            page.update()
            return

        urls = [line.strip() for line in raw_text.split("\n") if line.strip()]
        if not urls:
            status_text.value = "❌ မှန်ကန်သော Link မရှိပါ။"
            page.update()
            return

        for url in urls:
            fname = url.split('/')[-1].split('?')[0]
            fname = urllib.parse.unquote(fname) or "video.mp4"
            download_tasks[fname] = {
                'url': url, 'status': 'Waiting', 'percent': 0, 'speed': '0 KB/s', 
                'control': 'running', 'last_ui_update': 0
            }

        update_ui()
        status_text.value = f"🚀 4-Threads ဖြင့် အမြန်ဆွဲနေပါပြီ..."
        page.update()

        threading.Thread(target=queue_download_worker, daemon=True).start()

    # 4-Threads Download လုပ်မည့် Function
    def multi_thread_download(fname, url, file_path, total_size):
        num_threads = 4  
        part_size = total_size // num_threads
        parts_downloaded = [0] * num_threads
        start_time = time.time()

        def download_part(part_index, start_byte, end_byte):
            headers = {'Range': f'bytes={start_byte}-{end_byte}'}
            part_file = f"{file_path}.part{part_index}"
            try:
                res = requests.get(url, headers=headers, stream=True, timeout=15)
                with open(part_file, 'wb') as pf:
                    for chunk in res.iter_content(chunk_size=131072): 
                        while fname in download_tasks and download_tasks[fname]['control'] == 'paused':
                            time.sleep(0.5)
                        if fname not in download_tasks or download_tasks[fname]['control'] == 'stopped':
                            return
                        if chunk:
                            pf.write(chunk)
                            parts_downloaded[part_index] += len(chunk)
                            
                            total_dl = sum(parts_downloaded)
                            elapsed = time.time() - start_time
                            if elapsed > 0:
                                speed_bps = total_dl / elapsed
                                if speed_bps > 1024 * 1024:
                                    speed_str = f"{speed_bps / (1024*1024):.1f} MB/s"
                                else:
                                    speed_str = f"{speed_bps / 1024:.1f} KB/s"
                                download_tasks[fname]['speed'] = speed_str

                            download_tasks[fname]['percent'] = int((total_dl / total_size) * 100)
                            
                            if time.time() - download_tasks[fname].get('last_ui_update', 0) > 0.5:
                                download_tasks[fname]['last_ui_update'] = time.time()
                                update_ui()
            except Exception:
                pass

        threads = []
        for i in range(num_threads):
            start = i * part_size
            end = total_size - 1 if i == num_threads - 1 else (start + part_size - 1)
            t = threading.Thread(target=download_part, args=(i, start, end))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Stop နှိပ်ထားလျှင် ဖိုင်စများကို ပြန်ဖျက်မည်
        if fname not in download_tasks or download_tasks[fname]['control'] == 'stopped':
            for i in range(num_threads):
                pf = f"{file_path}.part{i}"
                if os.path.exists(pf):
                    os.remove(pf)
            return

        # ပြီးဆုံးလျှင် ဖိုင်စများကို ပေါင်းမည်
        if fname in download_tasks:
            download_tasks[fname]['status'] = 'Merging...'
            download_tasks[fname]['speed'] = 'Processing'
            update_ui()
            
        with open(file_path, 'wb') as outfile:
            for i in range(num_threads):
                part_file = f"{file_path}.part{i}"
                if os.path.exists(part_file):
                    with open(part_file, 'rb') as infile:
                        outfile.write(infile.read())
                    os.remove(part_file)

        if fname in download_tasks:
            finished_tasks[fname] = {'path': str(file_path)}
            del download_tasks[fname]
            update_ui()

    def queue_download_worker():
        while True:
            pending_files = [fname for fname, info in download_tasks.items() if info['status'] == 'Waiting']
            if not pending_files:
                break
            
            fname = pending_files[0]
            url = download_tasks[fname]['url']
            
            if os.name == 'nt':
                download_dir = Path.home() / "Downloads" / "DATA_PLUS"
            else:
                download_dir = Path("/storage/emulated/0/Download/DATA_PLUS")
                
            download_dir.mkdir(parents=True, exist_ok=True)
            file_path = download_dir / fname

            try:
                download_tasks[fname]['status'] = 'Downloading'
                update_ui()

                # ဖိုင်ဆိုဒ်ကို စစ်ဆေးခြင်း
                head_res = requests.head(url, allow_redirects=True, timeout=10)
                total_size = int(head_res.headers.get('content-length', 0))
                
                if total_size > 0:
                    multi_thread_download(fname, url, str(file_path), total_size)
                else:
                    # Thread ဖြင့် ဆွဲမရပါက ရိုးရိုး Single Thread ဖြင့် ဆွဲမည်
                    response = requests.get(url, stream=True, timeout=15)
                    downloaded = 0
                    start_time = time.time()
                    with open(file_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=524288):
                            while fname in download_tasks and download_tasks[fname]['control'] == 'paused':
                                time.sleep(0.5)
                            if fname not in download_tasks or download_tasks[fname]['control'] == 'stopped':
                                if os.path.exists(file_path):
                                    os.remove(file_path)
                                return

                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                elapsed = time.time() - start_time
                                if elapsed > 0:
                                    speed_bps = downloaded / elapsed
                                    if speed_bps > 1024 * 1024:
                                        download_tasks[fname]['speed'] = f"{speed_bps / (1024*1024):.1f} MB/s"
                                    else:
                                        download_tasks[fname]['speed'] = f"{speed_bps / 1024:.1f} KB/s"
                                
                                if time.time() - download_tasks[fname].get('last_ui_update', 0) > 0.5:
                                    download_tasks[fname]['last_ui_update'] = time.time()
                                    update_ui()

                    if fname in download_tasks:
                        finished_tasks[fname] = {'path': str(file_path)}
                        del download_tasks[fname]
                        update_ui()

            except Exception as ex:
                if fname in download_tasks:
                    download_tasks[fname]['status'] = 'Error'
                    download_tasks[fname]['speed'] = str(ex)[:20]
                    update_ui()

        status_text.value = "🎉 ဒေါင်းလုဒ် အားလုံး ပြီးစီးသွားပါပြီ!"
        page.update()

    paste_btn = ft.ElevatedButton(text="📋 Paste", on_click=paste_from_clipboard, bgcolor="#333333", color="#ffffff")
    clear_btn = ft.ElevatedButton(text="🗑️ Clear", on_click=clear_input, bgcolor="#552222", color="#ffffff")
    download_btn = ft.ElevatedButton(text="📥 ဒေါင်းလုဒ် စတင်ရန်", on_click=start_download, bgcolor="#0275d8", color="#ffffff")
    
    # Remove All ခလုတ်များ
    clear_downloading_btn = ft.ElevatedButton(text="🧹 Downloading အားလုံးဖျက်မည်", on_click=clear_downloading_list, bgcolor="#442255", color="#ffffff")
    clear_finished_btn = ft.ElevatedButton(text="🧹 Finished အားလုံးဖျက်မည်", on_click=clear_finished_list, bgcolor="#442255", color="#ffffff")

    content_area = ft.Container(
        content=ft.Column([
            ft.Row([clear_downloading_btn], alignment=ft.MainAxisAlignment.END),
            downloading_list
        ], spacing=5, expand=True), 
        bgcolor="#101010", padding=5, expand=True
    )

    def switch_to_downloading(e):
        tab_btn_1.bgcolor = "#333333"
        tab_btn_2.bgcolor = "#222222"
        tab_btn_1.update()
        tab_btn_2.update()
        content_area.content = ft.Column([
            ft.Row([clear_downloading_btn], alignment=ft.MainAxisAlignment.END),
            downloading_list
        ], spacing=5, expand=True)
        content_area.update()

    def switch_to_finished(e):
        tab_btn_2.bgcolor = "#333333"
        tab_btn_1.bgcolor = "#222222"
        tab_btn_1.update()
        tab_btn_2.update()
        content_area.content = ft.Column([
            ft.Row([clear_finished_btn], alignment=ft.MainAxisAlignment.END),
            finished_list
        ], spacing=5, expand=True)
        content_area.update()

    tab_btn_1.on_click = switch_to_downloading
    tab_btn_2.on_click = switch_to_finished

    page.add(
        ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("🎬 DATA PLUS Downloader", size=16, weight=ft.FontWeight.BOLD, color="#4a9eff")
                ], alignment=ft.MainAxisAlignment.CENTER),
                ft.Divider(color="#333333"),
                status_text,
                links_input,
                ft.Row([paste_btn, clear_btn, download_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(color="#333333"),
                ft.Row([tab_btn_1, tab_btn_2], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                content_area
            ], spacing=10, expand=True),
            bgcolor="#1a1a1a",
            padding=15,
            border_radius=20,
            expand=True
        )
    )

ft.app(target=main)
