from pathlib import Path
import argparse
import base64
import io
import json
import os
import platform
import queue
import subprocess
import sys
import threading
import core

VERSION = '1.1.0'

def assets():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / 'assets'

def gui(smoke=None):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('EmoSakura.WenkuTxtEpub')
    root = tk.Tk()
    root.title('轻小说文库 · TXT 转 EPUB ' + VERSION)
    root.geometry('880x800')
    root.minsize(820, 740)
    icon = tk.PhotoImage(file=str(assets() / 'icon-preview.png'))
    root.iconphoto(True, icon)
    if sys.platform == 'win32':
        root.iconbitmap(str(assets() / 'app.ico'))
    frame = ttk.Frame(root, padding=22)
    frame.pack(fill='both', expand=True)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(9, weight=1)
    title = ttk.Frame(frame)
    title.grid(row=0, column=0, sticky='ew', pady=(0, 14))
    small_icon = icon.subsample(4, 4)
    ttk.Label(title, image=small_icon).pack(side='left', padx=(0, 12))
    ttk.Label(title, text='小说下载与转换', font=('', 20, 'bold')).pack(side='left')
    ttk.Label(frame, text='读取文库或本地 TXT，选择分卷，导出 EPUB。').grid(row=1, column=0, sticky='w')
    cover_preview = ttk.Label(title, text='书籍封面', anchor='center')
    cover_preview.pack(side='right')
    link = tk.StringVar()
    link_entry = ttk.Entry(frame, textvariable=link)
    link_entry.grid(row=2, column=0, sticky='ew', pady=(12, 5))
    ttk.Label(frame, text='链接示例：https://www.wenku8.net/book/xxxxx.htm').grid(row=3, column=0, sticky='w')
    target = tk.StringVar(value=str(Path.home() / 'Downloads' / 'WenkuTxtEpub'))
    folder = ttk.Frame(frame)
    folder.grid(row=4, column=0, sticky='ew', pady=16)
    folder.columnconfigure(1, weight=1)
    ttk.Label(folder, text='保存位置  ').grid(row=0, column=0)
    ttk.Entry(folder, textvariable=target, state='readonly').grid(row=0, column=1, sticky='ew')
    def choose_folder():
        chosen = filedialog.askdirectory(parent=root)
        if chosen:
            target.set(chosen)
    choose = ttk.Button(folder, text='选择…', command=choose_folder)
    choose.grid(row=0, column=2, padx=(8, 0))
    buttons = ttk.Frame(frame)
    buttons.grid(row=5, column=0, sticky='w', pady=(0, 12))
    selection_frame = ttk.LabelFrame(frame, text='分卷（支持多选）', padding=8)
    selection_frame.grid(row=6, column=0, sticky='ew')
    volume_list = tk.Listbox(selection_frame, height=6, selectmode='multiple', exportselection=False)
    volume_list.pack(side='left', fill='both', expand=True)
    scrollbar = ttk.Scrollbar(selection_frame, command=volume_list.yview)
    scrollbar.pack(side='right', fill='y')
    volume_list.configure(yscrollcommand=scrollbar.set)
    export_bar = ttk.Frame(frame)
    export_bar.grid(row=7, column=0, sticky='ew', pady=10)
    ttk.Button(export_bar, text='全选', command=lambda: volume_list.selection_set(0, 'end')).pack(side='left')
    ttk.Button(export_bar, text='清空选择', command=lambda: volume_list.selection_clear(0, 'end')).pack(side='left', padx=8)
    merge = tk.BooleanVar(value=True)
    ttk.Checkbutton(export_bar, text='合并所选卷（取消勾选则每卷单独保存）', variable=merge).pack(side='left')
    save_txt = tk.BooleanVar(value=True)
    ttk.Checkbutton(export_bar, text='同时保存 TXT', variable=save_txt).pack(side='left', padx=8)
    log = tk.Text(frame, height=7, wrap='word', state='disabled')
    log.grid(row=9, column=0, sticky='nsew')
    progress = ttk.Progressbar(frame, mode='indeterminate')
    progress.grid(row=10, column=0, sticky='ew', pady=(10, 0))
    ttk.Label(frame, text='在线需先读取整本 TXT；仅导出所选卷。封面为网站书籍封面，不含正文插图。').grid(row=11, column=0, sticky='w', pady=(8, 0))
    events = queue.Queue()
    state = {'busy': False, 'book': None, 'cover': None}
    def show_cover(data):
        state['cover'] = data
        if data:
            from PIL import Image
            picture = Image.open(io.BytesIO(data))
            picture.thumbnail((68, 90))
            buffer = io.BytesIO()
            picture.save(buffer, format='PNG')
            state['preview'] = tk.PhotoImage(data=base64.b64encode(buffer.getvalue()))
            cover_preview.configure(image=state['preview'], text='')
        else:
            cover_preview.configure(image='', text='暂无封面')
    def write(message):
        log.configure(state='normal')
        log.insert('end', str(message) + '\n')
        log.see('end')
        log.configure(state='disabled')
    def job(function):
        if state['busy']:
            return
        state['busy'] = True
        progress.start(12)
        for widget in (download_button, local_button, choose, link_entry, export_button, cover_button):
            widget.configure(state='disabled')
        def worker():
            try:
                function()
            except Exception as error:
                events.put(('message', '未完成：' + str(error)))
            finally:
                events.put(('done', None))
        threading.Thread(target=worker, daemon=True).start()
    def from_link():
        url = link.get()
        state['book'] = None
        show_cover(None)
        volume_list.delete(0, 'end')
        def run():
            identifier = core.book_id(url)
            text = core.fetch_txt(identifier, lambda message: events.put(('message', message)))
            cover = core.fetch_cover(identifier, lambda message: events.put(('message', message)))
            events.put(('cover', cover))
            events.put(('book', (text, core.title_of(text, '文库小说_' + identifier), url)))
        job(run)
    def from_files():
        files = filedialog.askopenfilenames(parent=root, filetypes=[('TXT 文本', '*.txt')])
        if not files:
            return
        directory = target.get()
        state['book'] = None
        show_cover(None)
        volume_list.delete(0, 'end')
        def run():
            if len(files) == 1:
                file = Path(files[0])
                if file.stat().st_size > core.LIMIT:
                    raise ValueError('TXT 超过 80 MiB。')
                text = core.decode(file.read_bytes())
                events.put(('book', (text, core.title_of(text, file.stem), None)))
                return
            for file in files:
                try:
                    events.put(('message', '已保存：' + str(core.convert_file(file, directory))))
                except Exception as error:
                    events.put(('message', Path(file).name + '：' + str(error)))
        job(run)
    def export_selection():
        book = state['book']
        indexes = list(volume_list.curselection())
        if not book or not indexes:
            messagebox.showinfo('选择分卷', '请先读取 TXT 并选择至少一卷。', parent=root)
            return
        directory, combine, with_txt, cover = target.get(), merge.get(), save_txt.get(), state['cover']
        def run():
            for output in core.export_volumes(book[0], book[1], indexes, directory, combine, book[2], cover, with_txt):
                events.put(('message', '已保存：' + str(output)))
        job(run)
    def choose_cover():
        path = filedialog.askopenfilename(parent=root, filetypes=[('封面图片', '*.jpg *.jpeg *.png *.webp')])
        if path:
            try:
                if Path(path).stat().st_size > 10 * 1024 * 1024:
                    raise ValueError('封面超过 10 MiB。')
                show_cover(core.normalize_cover(Path(path).read_bytes()))
            except Exception as error:
                messagebox.showerror('无法读取封面', str(error), parent=root)
    def open_folder():
        try:
            path = Path(target.get())
            path.mkdir(parents=True, exist_ok=True)
            if sys.platform == 'win32':
                os.startfile(path)
            else:
                subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(path)])
        except Exception as error:
            messagebox.showerror('无法打开', str(error), parent=root)
    download_button = ttk.Button(buttons, text='读取在线卷目', command=from_link)
    download_button.pack(side='left', padx=(0, 10))
    local_button = ttk.Button(buttons, text='选择本地 TXT', command=from_files)
    local_button.pack(side='left', padx=(0, 10))
    ttk.Button(buttons, text='打开保存文件夹', command=open_folder).pack(side='left')
    cover_button = ttk.Button(buttons, text='选择封面…', command=choose_cover)
    cover_button.pack(side='left', padx=10)
    export_button = ttk.Button(frame, text='导出所选卷为 EPUB', command=export_selection, state='disabled')
    export_button.grid(row=8, column=0, sticky='w', pady=(0, 12))
    def poll():
        while True:
            try:
                kind, message = events.get_nowait()
            except queue.Empty:
                break
            if kind == 'done':
                state['busy'] = False
                progress.stop()
                for widget in (download_button, local_button, choose, link_entry, cover_button):
                    widget.configure(state='normal')
                export_button.configure(state='normal' if state['book'] else 'disabled')
            elif kind == 'cover':
                show_cover(message)
            elif kind == 'book':
                state['book'] = message
                volume_list.delete(0, 'end')
                for name, content in core.volumes(message[0]):
                    volume_list.insert('end', f'{name}  ·  {len(content):,} 字符')
                volume_list.selection_set(0, 'end')
                write('卷目已读取：' + message[1] + '。请选择分卷后导出。')
            else:
                write(message)
        root.after(100, poll)
    def close():
        if state['busy']:
            messagebox.showinfo('正在处理', '请等待任务完成后关闭窗口。', parent=root)
        else:
            root.destroy()
    root.protocol('WM_DELETE_WINDOW', close)
    write('准备就绪。')
    poll()
    if smoke:
        def finish():
            root.update_idletasks()
            report = {'version': VERSION, 'platform': platform.platform(), 'machine': platform.machine(), 'tk': root.tk.call('info', 'patchlevel'), 'window_visible': bool(root.winfo_viewable()), 'icon_size': [icon.width(), icon.height()], 'download_button': download_button.cget('text')}
            if not report['window_visible'] or report['icon_size'] != [256, 256]:
                raise RuntimeError('GUI smoke test failed')
            sample = '<GUI测试>\n第一卷 开始\n第一章 测试\n中文 & 内容。\n第二卷 继续\n第一章 测试\n第二卷正文。'
            state['book'] = (sample, 'GUI测试', None)
            volume_list.insert('end', '第一卷', '第二卷')
            volume_list.selection_clear(0, 'end')
            volume_list.selection_set(1)
            output_dir = Path(smoke).resolve().parent / 'gui-export'
            cover = core.normalize_cover((assets() / 'icon-preview.png').read_bytes())
            show_cover(cover)
            result = core.export_volumes(sample, 'GUI测试', list(volume_list.curselection()), output_dir, merge.get(), cover=cover, save_txt=True)
            core.verify(result[0])
            report['selected_volume_export'] = str(result[0])
            report['cover_preview'] = bool(state.get('preview'))
            report['txt_export'] = result[1].exists()
            Path(smoke).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            root.destroy()
        root.after(1200, finish)
    root.mainloop()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--convert', metavar='TXT')
    parser.add_argument('--output', metavar='FOLDER')
    parser.add_argument('--smoke-test', metavar='REPORT')
    parser.add_argument('--report', metavar='REPORT')
    args = parser.parse_args()
    if args.convert:
        result = core.convert_file(args.convert, args.output or '.')
        if args.report:
            Path(args.report).write_text(json.dumps({'epub': str(result), 'version': VERSION}), encoding='utf-8')
    else:
        gui(args.smoke_test)

if __name__ == '__main__':
    main()
