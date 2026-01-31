import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import requests
import threading
import time
import json
from datetime import datetime, timedelta
from urllib.parse import urlparse, unquote
import shutil
import base64


# VLC için gelişmiş path yönetimi
def setup_vlc():
    """VLC kütüphanesini kur"""
    vlc_loaded = False

    try:
        import vlc
        vlc_loaded = True
        print("VLC normal yüklendi")
    except ImportError:
        # EXE modunda VLC path'ini ayarla
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
            vlc_path = os.path.join(base_path, 'vlc')

            if os.path.exists(vlc_path):
                if sys.platform == "win32":
                    os.environ['PYTHON_VLC_LIB_PATH'] = os.path.join(vlc_path, 'libvlc.dll')
                    os.environ['VLC_PLUGIN_PATH'] = os.path.join(vlc_path, 'plugins')
                elif sys.platform.startswith('linux'):
                    os.environ['PYTHON_VLC_LIB_PATH'] = os.path.join(vlc_path, 'libvlc.so')
                    os.environ['VLC_PLUGIN_PATH'] = os.path.join(vlc_path, 'plugins')
                elif sys.platform == "darwin":
                    os.environ['PYTHON_VLC_LIB_PATH'] = os.path.join(vlc_path, 'libvlc.dylib')
                    os.environ['VLC_PLUGIN_PATH'] = os.path.join(vlc_path, 'plugins')

                try:
                    import vlc
                    vlc_loaded = True
                    print("VLC EXE modunda yüklendi")
                except ImportError as e:
                    print(f"VLC yükleme hatası: {e}")

    if not vlc_loaded:
        error_msg = """
VLC Media Player bulunamadı!

Lütfen aşağıdakilerden birini yapın:
1. VLC Media Player'ı yükleyin: https://www.videolan.org/vlc/
2. VLC'yi yükledikten sonra programı yeniden çalıştırın
"""
        tk.messagebox.showerror("VLC Gerekli", error_msg)
        sys.exit(1)

    return vlc


# VLC'yi yükle
vlc = setup_vlc()


class IPTVPlayer:
    def __init__(self, root):
        self.root = root
        self.root.title("Gelişmiş IPTV Player v3.0")
        self.root.geometry("1200x700")
        self.root.configure(bg='#2c3e50')

        # Veri yapıları
        self.playlists = {}
        self.current_playlist = None
        self.current_group = None
        self.favorites = self.load_favorites()
        self.fullscreen = False
        self.current_channel = None
        self.is_playing = False
        self.media_duration = 0
        self.current_playing_index = -1

        # UI kontrol değişkenleri
        self.left_frame_visible = True
        self.controls_visible = True
        self.auto_hide_timer = None

        # VLC player
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()

        # Arayüzü oluştur
        self.setup_ui()
        self.setup_menus()

        # Fare hareket takibi
        self.setup_mouse_tracking()

        # Sağ tık menüsü
        self.setup_context_menu()

        # Kayıtlı playlist'leri yükle
        self.load_saved_playlists()

        # Zaman güncelleme thread'ini başlat
        self.start_time_update()

    def safe_itemconfig(self, listbox, index, config):
        """Listbox item config işlemini güvenli şekilde yapar"""
        try:
            if index != -1 and index < listbox.size():
                listbox.itemconfig(index, config)
        except tk.TclError:
            pass

    def setup_ui(self):
        # Ana frame
        self.main_frame = tk.Frame(self.root, bg='#2c3e50')
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Üst bilgi çubuğu
        self.setup_top_info()

        # Sol panel - Playlist ve kanal listesi
        self.setup_left_panel()

        # Sağ panel - Video player
        self.setup_right_panel()

    def setup_top_info(self):
        """Üstte oynatılan kanal bilgisi"""
        self.top_info_frame = tk.Frame(self.main_frame, bg='#34495e', height=30)
        self.top_info_frame.pack(fill=tk.X, pady=(0, 10))
        self.top_info_frame.pack_propagate(False)

        self.current_channel_label = tk.Label(
            self.top_info_frame,
            text="🎬 Oynatılan: Hiçbir kanal seçilmedi",
            bg='#34495e',
            fg='#2ecc71',
            font=('Arial', 11, 'bold')
        )
        self.current_channel_label.pack(side=tk.LEFT, padx=10, pady=5)

    def setup_left_panel(self):
        """Sol paneli kur"""
        self.left_frame = tk.Frame(self.main_frame, bg='#34495e', width=300)
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.left_frame.pack_propagate(False)

        # Playlist yönetimi
        playlist_frame = tk.Frame(self.left_frame, bg='#34495e')
        playlist_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(playlist_frame, text="📺 IPTV PLAYLISTS", bg='#34495e',
                 fg='white', font=('Arial', 12, 'bold')).pack(anchor=tk.W)

        # Playlist ekleme butonları
        btn_frame = tk.Frame(playlist_frame, bg='#34495e')
        btn_frame.pack(fill=tk.X, pady=5)

        tk.Button(btn_frame, text="🌐 URL Ekle", command=self.add_url_playlist,
                  bg='#3498db', fg='white', relief=tk.FLAT, font=('Arial', 9)).pack(side=tk.LEFT, fill=tk.X,
                                                                                    expand=True, padx=(0, 2))
        tk.Button(btn_frame, text="📁 Dosya Ekle", command=self.add_file_playlist,
                  bg='#2ecc71', fg='white', relief=tk.FLAT, font=('Arial', 9)).pack(side=tk.LEFT, fill=tk.X,
                                                                                    expand=True, padx=(2, 0))

        # Xtreme Codes butonu
        tk.Button(btn_frame, text="⚡ Xtreme Ekle", command=self.add_xtreme_playlist,
                  bg='#e74c3c', fg='white', relief=tk.FLAT, font=('Arial', 9)).pack(side=tk.LEFT, fill=tk.X,
                                                                                    expand=True, padx=(2, 0))

        # Playlist listbox
        listbox_frame = tk.Frame(playlist_frame, bg='#34495e')
        listbox_frame.pack(fill=tk.X, pady=5)

        self.playlist_listbox = tk.Listbox(listbox_frame, bg='#2c3e50', fg='white',
                                           selectbackground='#3498db', height=6,
                                           font=('Arial', 9))
        self.playlist_listbox.pack(fill=tk.X)
        self.playlist_listbox.bind('<<ListboxSelect>>', self.on_playlist_select)

        # Gruplar
        group_frame = tk.Frame(self.left_frame, bg='#34495e')
        group_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(group_frame, text="📋 KANAL GRUPLARI", bg='#34495e',
                 fg='white', font=('Arial', 12, 'bold')).pack(anchor=tk.W)

        self.group_combobox = ttk.Combobox(group_frame, state="readonly", font=('Arial', 9))
        self.group_combobox.pack(fill=tk.X, pady=5)
        self.group_combobox.bind('<<ComboboxSelected>>', self.on_group_select)

        # Kanal listesi
        channel_list_frame = tk.Frame(self.left_frame, bg='#34495e')
        channel_list_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollbar for channel list
        channel_scrollbar = tk.Scrollbar(channel_list_frame)
        channel_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.channel_listbox = tk.Listbox(channel_list_frame, bg='#2c3e50', fg='white',
                                          selectbackground='#3498db', yscrollcommand=channel_scrollbar.set,
                                          font=('Arial', 9))
        self.channel_listbox.pack(fill=tk.BOTH, expand=True)
        channel_scrollbar.config(command=self.channel_listbox.yview)

        self.channel_listbox.bind('<Double-Button-1>', self.on_channel_double_click)
        self.channel_listbox.bind('<Button-3>', self.show_channel_context_menu)

        # Favori butonu
        fav_frame = tk.Frame(self.left_frame, bg='#34495e')
        fav_frame.pack(fill=tk.X, pady=(10, 0))

        self.fav_button = tk.Button(fav_frame, text="⭐ Favorilere Ekle",
                                    command=self.toggle_favorite,
                                    bg='#f39c12', fg='white', relief=tk.FLAT,
                                    font=('Arial', 10, 'bold'))
        self.fav_button.pack(fill=tk.X)

    def setup_right_panel(self):
        """Sağ paneli kur"""
        self.right_frame = tk.Frame(self.main_frame, bg='#1c1c1c')
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Video canvas
        self.video_frame = tk.Frame(self.right_frame, bg='black')
        self.video_frame.pack(fill=tk.BOTH, expand=True)
        self.video_frame.bind('<Double-Button-1>', self.toggle_fullscreen)
        self.video_frame.bind('<Button-3>', self.show_video_context_menu)

        # İlerleme çubuğu ve zaman bilgisi
        self.setup_progress_controls(self.right_frame)

        # Kontrol paneli
        self.setup_control_panel(self.right_frame)

    def setup_progress_controls(self, parent):
        """Video ilerleme çubuğu ve zaman bilgilerini kur"""
        self.progress_frame = tk.Frame(parent, bg='#34495e')
        self.progress_frame.pack(fill=tk.X, pady=(5, 0))

        # Zaman bilgileri
        time_frame = tk.Frame(self.progress_frame, bg='#34495e')
        time_frame.pack(fill=tk.X, padx=10, pady=5)

        self.current_time_label = tk.Label(time_frame, text="00:00:00",
                                           bg='#34495e', fg='white', font=('Arial', 10))
        self.current_time_label.pack(side=tk.LEFT)

        self.duration_label = tk.Label(time_frame, text="00:00:00",
                                       bg='#34495e', fg='white', font=('Arial', 10))
        self.duration_label.pack(side=tk.RIGHT)

        # İlerleme çubuğu
        self.progress_scale = tk.Scale(self.progress_frame, from_=0, to=100,
                                       orient=tk.HORIZONTAL, command=self.on_progress_scale,
                                       bg='#34495e', fg='white', troughcolor='#2c3e50',
                                       highlightbackground='#34495e', length=400,
                                       showvalue=False)
        self.progress_scale.pack(fill=tk.X, padx=10, pady=5)
        self.progress_scale.bind('<Button-1>', self.on_progress_click)

    def setup_control_panel(self, parent):
        """Video kontrol panelini kur"""
        self.control_frame = tk.Frame(parent, bg='#34495e')
        self.control_frame.pack(fill=tk.X, pady=(10, 0))

        # Sol taraf - Temel kontroller
        left_controls = tk.Frame(self.control_frame, bg='#34495e')
        left_controls.pack(side=tk.LEFT, padx=10, pady=5)

        tk.Button(left_controls, text="⏮️", command=self.previous_channel,
                  bg='#3498db', fg='white', relief=tk.FLAT, font=('Arial', 10)).pack(side=tk.LEFT, padx=2)
        tk.Button(left_controls, text="⏸️", command=self.pause_video,
                  bg='#e74c3c', fg='white', relief=tk.FLAT, font=('Arial', 10)).pack(side=tk.LEFT, padx=2)
        tk.Button(left_controls, text="▶️", command=self.play_video,
                  bg='#2ecc71', fg='white', relief=tk.FLAT, font=('Arial', 10)).pack(side=tk.LEFT, padx=2)
        tk.Button(left_controls, text="⏭️", command=self.next_channel,
                  bg='#3498db', fg='white', relief=tk.FLAT, font=('Arial', 10)).pack(side=tk.LEFT, padx=2)
        tk.Button(left_controls, text="⏹️", command=self.stop_video,
                  bg='#95a5a6', fg='white', relief=tk.FLAT, font=('Arial', 10)).pack(side=tk.LEFT, padx=2)

        # Sağ taraf - Ses kontrolü
        right_controls = tk.Frame(self.control_frame, bg='#34495e')
        right_controls.pack(side=tk.RIGHT, padx=10, pady=5)

        tk.Label(right_controls, text="🔊", bg='#34495e', fg='white').pack(side=tk.LEFT)
        self.volume_scale = tk.Scale(right_controls, from_=0, to=100, orient=tk.HORIZONTAL,
                                     command=self.set_volume, bg='#34495e', fg='white',
                                     highlightbackground='#34495e', length=100,
                                     showvalue=True)
        self.volume_scale.set(50)
        self.volume_scale.pack(side=tk.LEFT, padx=5)

    def setup_menus(self):
        """Menü çubuğunu oluştur"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # Dosya menüsü
        file_menu = tk.Menu(menubar, tearoff=0, bg='#34495e', fg='white')
        menubar.add_cascade(label="📁 Dosya", menu=file_menu)
        file_menu.add_command(label="🌐 URL'den Playlist Ekle", command=self.add_url_playlist)
        file_menu.add_command(label="📁 Dosyadan Playlist Ekle", command=self.add_file_playlist)
        file_menu.add_command(label="⚡ Xtreme Codes Ekle", command=self.add_xtreme_playlist)
        file_menu.add_separator()
        file_menu.add_command(label="🔧 Playlist Yönet", command=self.show_playlist_manager)
        file_menu.add_separator()
        file_menu.add_command(label="🚪 Çıkış", command=self.root.quit)

        # Görünüm menüsü
        view_menu = tk.Menu(menubar, tearoff=0, bg='#34495e', fg='white')
        menubar.add_cascade(label="👁️ Görünüm", menu=view_menu)
        view_menu.add_command(label="🖥️ Tam Ekran", command=self.toggle_fullscreen_menu, accelerator="F11")
        view_menu.add_command(label="⭐ Favoriler", command=self.show_favorites, accelerator="Ctrl+F")
        view_menu.add_separator()
        view_menu.add_command(label="📊 Arayüzü Sıfırla", command=self.reset_ui)

        # Oynatma menüsü
        playback_menu = tk.Menu(menubar, tearoff=0, bg='#34495e', fg='white')
        menubar.add_cascade(label="🎮 Oynatma", menu=playback_menu)
        playback_menu.add_command(label="⏮️ Önceki Kanal", command=self.previous_channel, accelerator="Ctrl+Left")
        playback_menu.add_command(label="⏭️ Sonraki Kanal", command=self.next_channel, accelerator="Ctrl+Right")
        playback_menu.add_separator()
        playback_menu.add_command(label="⏪ 10 saniye geri", command=self.seek_backward, accelerator="Left")
        playback_menu.add_command(label="⏩ 10 saniye ileri", command=self.seek_forward, accelerator="Right")
        playback_menu.add_separator()
        playback_menu.add_command(label="🔊 Sesi Aç", command=self.volume_up, accelerator="Up")
        playback_menu.add_command(label="🔇 Sesi Kıs", command=self.volume_down, accelerator="Down")

        # Araçlar menüsü
        tools_menu = tk.Menu(menubar, tearoff=0, bg='#34495e', fg='white')
        menubar.add_cascade(label="🔧 Araçlar", menu=tools_menu)
        tools_menu.add_command(label="🔍 Kanal Arama", command=self.search_channels)
        tools_menu.add_command(label="🔄 Tüm Listeleri Güncelle", command=self.update_all_playlists)
        tools_menu.add_command(label="📊 Playlist İstatistikleri", command=self.show_stats)

        # Ayarlar menüsü
        settings_menu = tk.Menu(menubar, tearoff=0, bg='#34495e', fg='white')
        menubar.add_cascade(label="⚙️ Ayarlar", menu=settings_menu)
        settings_menu.add_command(label="🎯 Uygulama Ayarları", command=self.show_settings)
        settings_menu.add_command(label="🎨 Görünüm Ayarları", command=self.show_appearance_settings)
        settings_menu.add_command(label="📺 Oynatma Ayarları", command=self.show_playback_settings)

        # Yardım menüsü
        help_menu = tk.Menu(menubar, tearoff=0, bg='#34495e', fg='white')
        menubar.add_cascade(label="❓ Yardım", menu=help_menu)
        help_menu.add_command(label="📖 Kullanım Kılavuzu", command=self.show_help)
        help_menu.add_command(label="ℹ️ Hakkında", command=self.show_about)

        # Klavye kısayolları
        self.root.bind('<F11>', self.toggle_fullscreen)
        self.root.bind('<Control-f>', lambda e: self.show_favorites())
        self.root.bind('<Control-Left>', lambda e: self.previous_channel())
        self.root.bind('<Control-Right>', lambda e: self.next_channel())
        self.root.bind('<Left>', lambda e: self.seek_backward())
        self.root.bind('<Right>', lambda e: self.seek_forward())
        self.root.bind('<Up>', lambda e: self.volume_up())
        self.root.bind('<Down>', lambda e: self.volume_down())

    def setup_mouse_tracking(self):
        """Fare hareket takibini başlat"""
        widgets = [self.root, self.main_frame, self.left_frame, self.right_frame,
                   self.video_frame, self.control_frame, self.progress_frame]

        for widget in widgets:
            widget.bind('<Motion>', self.on_mouse_move)
            widget.bind('<Enter>', self.on_mouse_enter)
            widget.bind('<Leave>', self.on_mouse_leave)

        self.start_auto_hide()

    def setup_context_menu(self):
        """Sağ tık menüsünü kur"""
        # Video context menu
        self.video_context_menu = tk.Menu(self.root, tearoff=0, bg='#34495e', fg='white')
        self.video_context_menu.add_command(label="⭐ Favorilere Ekle/Çıkar", command=self.toggle_favorite)
        self.video_context_menu.add_separator()
        self.video_context_menu.add_command(label="⏸️ Duraklat", command=self.pause_video)
        self.video_context_menu.add_command(label="▶️ Devam Et", command=self.play_video)
        self.video_context_menu.add_separator()
        self.video_context_menu.add_command(label="🖥️ Tam Ekran", command=self.toggle_fullscreen)

        # Kanal listesi context menu
        self.channel_context_menu = tk.Menu(self.root, tearoff=0, bg='#34495e', fg='white')
        self.channel_context_menu.add_command(label="⭐ Favorilere Ekle/Çıkar", command=self.toggle_favorite)
        self.channel_context_menu.add_separator()
        self.channel_context_menu.add_command(label="🔍 Kanal Bilgisi", command=self.show_channel_info)

    def show_video_context_menu(self, event):
        """Video üzerinde sağ tık menüsü"""
        try:
            self.video_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.video_context_menu.grab_release()

    def show_channel_context_menu(self, event):
        """Kanal listesinde sağ tık menüsü"""
        try:
            # Tıklanan öğeyi seç
            widget = event.widget
            index = widget.nearest(event.y)
            widget.selection_clear(0, tk.END)
            widget.selection_set(index)
            widget.activate(index)

            self.channel_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.channel_context_menu.grab_release()

    def show_channel_info(self):
        """Kanal bilgilerini göster"""
        if hasattr(self, 'current_channel') and self.current_channel:
            channel = self.current_channel
            info = f"""
📺 Kanal Bilgisi:

🎬 İsim: {channel['name']}
📁 Grup: {channel['group']}
🔗 URL: {channel['url'][:100]}...
⭐ Favori: {'Evet' if self.is_favorite(channel) else 'Hayır'}
            """
            messagebox.showinfo("Kanal Bilgisi", info)

    def on_mouse_move(self, event):
        """Fare hareket ettiğinde"""
        if self.fullscreen:
            self.show_controls_temporarily()

            # Sol kenara yakınsa playlist panelini göster
            if event.x_root < 50:
                self.show_left_frame()
            else:
                self.hide_left_frame_after_delay()

            # Alt kenara yakınsa kontrolleri göster
            if event.y_root > self.root.winfo_screenheight() - 40:
                self.show_controls()
            else:
                self.hide_controls_after_delay()

    def on_mouse_enter(self, event):
        """Fare widget'a girdiğinde"""
        if self.fullscreen:
            self.show_controls_temporarily()

    def on_mouse_leave(self, event):
        """Fare widget'tan çıktığında"""
        if self.fullscreen:
            self.hide_controls_after_delay()
            self.hide_left_frame_after_delay()

    def show_controls_temporarily(self):
        """Kontrolleri geçici olarak göster"""
        if self.fullscreen:
            self.show_controls()
            self.hide_controls_after_delay()

    def show_controls(self):
        """Kontrolleri göster"""
        if self.fullscreen and not self.controls_visible:
            self.control_frame.pack(fill=tk.X, pady=(10, 0))
            self.progress_frame.pack(fill=tk.X, pady=(5, 0))
            self.controls_visible = True

    def hide_controls(self):
        """Kontrolleri gizle"""
        if self.fullscreen and self.controls_visible:
            self.control_frame.pack_forget()
            self.progress_frame.pack_forget()
            self.controls_visible = False

    def hide_controls_after_delay(self):
        """Kontrolleri belirli süre sonra gizle"""
        if self.auto_hide_timer:
            self.root.after_cancel(self.auto_hide_timer)
        self.auto_hide_timer = self.root.after(3000, self.hide_controls)

    def show_left_frame(self):
        """Sol frame'i göster"""
        if self.fullscreen and not self.left_frame_visible:
            self.left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
            self.left_frame_visible = True

    def hide_left_frame(self):
        """Sol frame'i gizle"""
        if self.fullscreen and self.left_frame_visible:
            self.left_frame.pack_forget()
            self.left_frame_visible = False

    def hide_left_frame_after_delay(self):
        """Sol frame'i belirli süre sonra gizle"""
        if self.auto_hide_timer:
            self.root.after_cancel(self.auto_hide_timer)
        self.auto_hide_timer = self.root.after(3000, self.hide_left_frame)

    def start_auto_hide(self):
        """Otomatik gizleme timer'ını başlat"""
        if self.fullscreen:
            self.hide_controls_after_delay()
            self.hide_left_frame_after_delay()

    def start_time_update(self):
        """Zaman güncelleme thread'ini başlat"""

        def update_time():
            while True:
                if self.is_playing:
                    current_time = self.player.get_time() // 1000
                    duration = self.media_duration // 1000

                    if duration > 0:
                        progress = (current_time / duration) * 100
                        self.root.after(0, lambda: self.update_progress_ui(current_time, duration, progress))

                time.sleep(1)

        threading.Thread(target=update_time, daemon=True).start()

    def update_progress_ui(self, current_time, duration, progress):
        """İlerleme çubuğu ve zaman etiketlerini güncelle"""
        if not hasattr(self, 'progress_dragging') or not self.progress_dragging:
            self.progress_scale.set(progress)

        current_str = self.format_time(current_time)
        duration_str = self.format_time(duration)

        self.current_time_label.config(text=current_str)
        self.duration_label.config(text=duration_str)

    def format_time(self, seconds):
        """Saniyeyi saat:dakika:saniye formatına çevir"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def on_progress_scale(self, value):
        """İlerleme çubuğu değiştiğinde"""
        if hasattr(self, 'progress_dragging') and self.progress_dragging:
            progress = float(value)
            if self.media_duration > 0:
                new_time = int((progress / 100) * self.media_duration)
                self.player.set_time(new_time)

    def on_progress_click(self, event):
        """İlerleme çubuğuna tıklandığında"""
        self.progress_dragging = True

        def release(event):
            self.progress_dragging = False

        self.progress_scale.bind('<ButtonRelease-1>', release)

    def add_url_playlist(self):
        url = simpledialog.askstring("Playlist Ekle", "M3U URL'sini girin:")
        if url:
            name = simpledialog.askstring("Playlist Adı", "Playlist için bir ad girin:")
            if name:
                threading.Thread(target=self.download_playlist, args=(url, name), daemon=True).start()

    def add_file_playlist(self):
        file_path = filedialog.askopenfilename(
            title="M3U Dosyası Seçin",
            filetypes=[("M3U files", "*.m3u"), ("M3U8 files", "*.m3u8"), ("All files", "*.*")]
        )
        if file_path:
            playlist_dir = "playlists"
            if not os.path.exists(playlist_dir):
                os.makedirs(playlist_dir)

            filename = os.path.basename(file_path)
            name = os.path.splitext(filename)[0]

            dest_path = os.path.join(playlist_dir, filename)

            try:
                shutil.copy2(file_path, dest_path)
                self.load_playlist_from_file(dest_path, name)
                messagebox.showinfo("Başarılı", f"'{name}' playlist'i eklendi ve kaydedildi!")
            except Exception as e:
                messagebox.showerror("Hata", f"Playlist kopyalanamadı: {str(e)}")

    def add_xtreme_playlist(self):
        """Xtreme Codes formatında playlist ekle"""
        url = simpledialog.askstring("Xtreme Codes Ekle",
                                     "Xtreme Codes URL'sini girin:\n(Örnek: http://example.com:8080/get.php?username=XXX&password=XXX&type=m3u)")
        if url:
            name = simpledialog.askstring("Playlist Adı", "Playlist için bir ad girin:")
            if name:
                # Xtreme Codes formatını işle
                if 'get.php' in url and 'type=m3u' in url:
                    threading.Thread(target=self.download_playlist, args=(url, name, True), daemon=True).start()
                else:
                    messagebox.showwarning("Uyarı", "Bu Xtreme Codes URL'si gibi görünmüyor. Yine de devam edilsin mi?",
                                           parent=self.root)

    def download_playlist(self, url, name, is_xtreme=False):
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                playlist_dir = "playlists"
                if not os.path.exists(playlist_dir):
                    os.makedirs(playlist_dir)

                file_path = os.path.join(playlist_dir, f"{name}.m3u")
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)

                self.root.after(0, lambda: self.complete_playlist_update(file_path, name, url, is_xtreme))
            else:
                self.root.after(0, lambda: messagebox.showerror("Hata", "Playlist indirilemedi!"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Hata", f"İndirme hatası: {str(e)}"))

    def complete_playlist_update(self, file_path, name, url, is_xtreme=False):
        self.load_playlist_from_file(file_path, name)
        if name in self.playlists:
            self.playlists[name]['url'] = url
            self.playlists[name]['is_xtreme'] = is_xtreme

        badge = " ⚡" if is_xtreme else ""
        messagebox.showinfo("Başarılı", f"'{name}'{badge} playlist'i eklendi ve kaydedildi!")

    def load_playlist_from_file(self, file_path, name):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            channels = self.parse_m3u(content)
            self.playlists[name] = {
                'file_path': file_path,
                'channels': channels,
                'groups': self.extract_groups(channels),
                'url': self.playlists.get(name, {}).get('url'),
                'is_xtreme': self.playlists.get(name, {}).get('is_xtreme', False)
            }

            self.update_playlist_listbox()

        except Exception as e:
            messagebox.showerror("Hata", f"Playlist yüklenemedi: {str(e)}")

    def parse_m3u(self, content):
        channels = []
        lines = content.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('#EXTINF:'):
                info_line = line[8:]

                attributes = {}
                if ',' in info_line:
                    title_part = info_line.split(',')[-1]
                    attr_part = info_line.split(',')[0]

                    # Grup bilgisini çıkar
                    if 'group-title=' in attr_part:
                        start = attr_part.find('group-title="') + 13
                        end = attr_part.find('"', start)
                        attributes['group-title'] = attr_part[start:end] if start != -1 and end != -1 else "Diğer"
                    else:
                        attributes['group-title'] = "Diğer"
                else:
                    title_part = info_line
                    attributes['group-title'] = "Diğer"

                if i + 1 < len(lines):
                    url = lines[i + 1].strip()
                    if url and not url.startswith('#'):
                        channel = {
                            'name': title_part,
                            'url': url,
                            'group': attributes.get('group-title', 'Diğer')
                        }
                        channels.append(channel)
                        i += 1
            i += 1

        return channels

    def extract_groups(self, channels):
        groups = set()
        for channel in channels:
            groups.add(channel['group'])
        return sorted(list(groups))

    def update_playlist_listbox(self):
        self.playlist_listbox.delete(0, tk.END)
        for name, data in self.playlists.items():
            display_name = name
            if data.get('is_xtreme', False):
                display_name += " ⚡"
            self.playlist_listbox.insert(tk.END, display_name)

    def on_playlist_select(self, event):
        selection = self.playlist_listbox.curselection()
        if selection:
            name_with_badge = self.playlist_listbox.get(selection[0])
            name = name_with_badge.replace(" ⚡", "")
            self.current_playlist = name
            # Aktif kanal indeksini sıfırla
            self.current_playing_index = -1
            self.update_group_combobox()

    def update_group_combobox(self):
        if self.current_playlist:
            groups = self.playlists[self.current_playlist]['groups']
            self.group_combobox['values'] = groups
            if groups:
                self.group_combobox.set(groups[0])
                self.on_group_select()

    def on_group_select(self, event=None):
        if self.current_playlist and self.group_combobox.get():
            self.current_group = self.group_combobox.get()
            # Aktif kanal indeksini sıfırla
            self.current_playing_index = -1
            self.update_channel_listbox()

    def update_channel_listbox(self):
        self.channel_listbox.delete(0, tk.END)
        if self.current_playlist and self.current_group:
            channels = self.playlists[self.current_playlist]['channels']
            for i, channel in enumerate(channels):
                if channel['group'] == self.current_group:
                    display_name = channel['name']
                    if self.is_favorite(channel):
                        display_name = "⭐ " + display_name

                    self.channel_listbox.insert(tk.END, display_name)

                    # Şu an oynatılan kanalı işaretle (geçerli indeks kontrolü ile)
                    if (hasattr(self, 'current_channel') and self.current_channel and
                            self.current_channel['name'] == channel['name'] and
                            self.current_channel['group'] == channel['group']):
                        self.current_playing_index = i
                        self.safe_itemconfig(self.channel_listbox, i, {'bg': '#3498db', 'fg': 'white'})

    def on_channel_double_click(self, event):
        selection = self.channel_listbox.curselection()
        if selection and self.current_playlist and self.current_group:
            channel_index = selection[0]
            channel_name = self.channel_listbox.get(channel_index).replace("⭐ ", "")
            channels = self.playlists[self.current_playlist]['channels']

            # Önceki aktif kanalın rengini sıfırla (geçerli indeks kontrolü ile)
            self.safe_itemconfig(self.channel_listbox, self.current_playing_index, {'bg': '#2c3e50', 'fg': 'white'})

            for channel in channels:
                if channel['name'] == channel_name and channel['group'] == self.current_group:
                    self.play_channel(channel)
                    # Yeni aktif kanalı işaretle
                    self.current_playing_index = channel_index
                    self.safe_itemconfig(self.channel_listbox, channel_index, {'bg': '#3498db', 'fg': 'white'})
                    break

    def play_channel(self, channel):
        try:
            media = self.instance.media_new(channel['url'])
            self.player.set_media(media)

            if os.name == 'nt':
                self.player.set_hwnd(self.video_frame.winfo_id())
            else:
                self.player.set_xwindow(self.video_frame.winfo_id())

            self.player.play()
            self.current_channel = channel
            self.is_playing = True

            # Üst bilgiyi güncelle
            self.current_channel_label.config(
                text=f"🎬 Oynatılan: {channel['name']} | 📁 {channel['group']}"
            )

            def get_duration():
                time.sleep(2)
                self.media_duration = self.player.get_length()

            threading.Thread(target=get_duration, daemon=True).start()

            self.update_fav_button()

        except Exception as e:
            messagebox.showerror("Hata", f"Kanal oynatılamadı: {str(e)}")

    def toggle_fullscreen(self, event=None):
        self.fullscreen = not self.fullscreen

        if self.fullscreen:
            self.root.attributes('-fullscreen', True)
            self.hide_left_frame()
            self.hide_controls()
            self.start_auto_hide()
        else:
            self.root.attributes('-fullscreen', False)
            self.root.geometry("1200x700")
            self.show_left_frame()
            self.show_controls()

            if self.auto_hide_timer:
                self.root.after_cancel(self.auto_hide_timer)

    def toggle_fullscreen_menu(self):
        self.toggle_fullscreen()

    def pause_video(self):
        self.player.pause()
        self.is_playing = not self.player.get_state() == vlc.State.Paused

    def play_video(self):
        self.player.play()
        self.is_playing = True

    def stop_video(self):
        self.player.stop()
        self.is_playing = False
        self.progress_scale.set(0)
        self.current_time_label.config(text="00:00:00")
        self.duration_label.config(text="00:00:00")
        self.current_channel_label.config(text="🎬 Oynatılan: Hiçbir kanal seçilmedi")

        # Aktif kanalın rengini sıfırla
        self.safe_itemconfig(self.channel_listbox, self.current_playing_index, {'bg': '#2c3e50', 'fg': 'white'})
        self.current_playing_index = -1

    def set_volume(self, value):
        self.player.audio_set_volume(int(value))

    def previous_channel(self):
        if self.current_playlist and self.current_group:
            selection = self.channel_listbox.curselection()
            current_index = selection[0] if selection else 0
            if current_index > 0:
                self.channel_listbox.selection_clear(0, tk.END)
                self.channel_listbox.selection_set(current_index - 1)
                self.channel_listbox.activate(current_index - 1)
                self.on_channel_double_click(None)

    def next_channel(self):
        if self.current_playlist and self.current_group:
            selection = self.channel_listbox.curselection()
            current_index = selection[0] if selection else 0
            if current_index < self.channel_listbox.size() - 1:
                self.channel_listbox.selection_clear(0, tk.END)
                self.channel_listbox.selection_set(current_index + 1)
                self.channel_listbox.activate(current_index + 1)
                self.on_channel_double_click(None)

    def seek_forward(self):
        current_time = self.player.get_time() + 10000
        self.player.set_time(current_time)

    def seek_backward(self):
        current_time = max(0, self.player.get_time() - 10000)
        self.player.set_time(current_time)

    def volume_up(self):
        current_volume = self.player.audio_get_volume()
        new_volume = min(100, current_volume + 10)
        self.player.audio_set_volume(new_volume)
        self.volume_scale.set(new_volume)

    def volume_down(self):
        current_volume = self.player.audio_get_volume()
        new_volume = max(0, current_volume - 10)
        self.player.audio_set_volume(new_volume)
        self.volume_scale.set(new_volume)

    def toggle_favorite(self):
        if hasattr(self, 'current_channel') and self.current_channel:
            channel_id = self.get_channel_id(self.current_channel)

            if channel_id in self.favorites:
                self.favorites.remove(channel_id)
                messagebox.showinfo("Favoriler", "Kanal favorilerden çıkarıldı!")
            else:
                self.favorites.append(channel_id)
                messagebox.showinfo("Favoriler", "Kanal favorilere eklendi!")

            self.save_favorites()
            self.update_fav_button()
            self.update_channel_listbox()
        else:
            messagebox.showwarning("Uyarı", "Önce bir kanal seçin!")

    def is_favorite(self, channel):
        channel_id = self.get_channel_id(channel)
        return channel_id in self.favorites

    def get_channel_id(self, channel):
        return f"{channel['name']}|{channel['url']}|{channel['group']}"

    def update_fav_button(self):
        if hasattr(self, 'current_channel') and self.current_channel:
            if self.is_favorite(self.current_channel):
                self.fav_button.config(text="⭐ Favorilerden Çıkar", bg='#e74c3c')
            else:
                self.fav_button.config(text="⭐ Favorilere Ekle", bg='#f39c12')
        else:
            self.fav_button.config(text="⭐ Favorilere Ekle", bg='#f39c12')

    def load_favorites(self):
        try:
            if os.path.exists('favorites.json'):
                with open('favorites.json', 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return []

    def save_favorites(self):
        try:
            with open('favorites.json', 'w', encoding='utf-8') as f:
                json.dump(self.favorites, f, ensure_ascii=False, indent=2)
        except:
            pass

    def load_saved_playlists(self):
        playlist_dir = "playlists"
        if os.path.exists(playlist_dir):
            for file in os.listdir(playlist_dir):
                if file.endswith('.m3u') or file.endswith('.m3u8'):
                    name = os.path.splitext(file)[0]
                    file_path = os.path.join(playlist_dir, file)
                    self.load_playlist_from_file(file_path, name)

    # Menü fonksiyonları
    def show_playlist_manager(self):
        manager_window = tk.Toplevel(self.root)
        manager_window.title("Playlist Yönetimi")
        manager_window.geometry("500x400")
        manager_window.configure(bg='#2c3e50')

        list_frame = tk.Frame(manager_window, bg='#2c3e50')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(list_frame, text="Mevcut Playlist'ler", font=('Arial', 11, 'bold'),
                 bg='#2c3e50', fg='white').pack(anchor=tk.W)

        playlist_listbox = tk.Listbox(list_frame, bg='#34495e', fg='white', height=10)
        playlist_listbox.pack(fill=tk.BOTH, expand=True, pady=5)

        for name, data in self.playlists.items():
            display_name = name
            if data.get('is_xtreme', False):
                display_name += " ⚡"
            playlist_listbox.insert(tk.END, display_name)

        btn_frame = tk.Frame(manager_window, bg='#2c3e50')
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Button(btn_frame, text="🔄 Güncelle",
                  command=lambda: self.update_selected_playlist(playlist_listbox),
                  bg='#3498db', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="🗑️ Sil",
                  command=lambda: self.delete_playlist(playlist_listbox),
                  bg='#e74c3c', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="📊 İstatistik",
                  command=lambda: self.show_playlist_stats(playlist_listbox),
                  bg='#9b59b6', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="❌ Kapat",
                  command=manager_window.destroy,
                  bg='#95a5a6', fg='white').pack(side=tk.RIGHT, padx=5)

    def show_favorites(self, event=None):
        favorites_window = tk.Toplevel(self.root)
        favorites_window.title("Favori Kanallar")
        favorites_window.geometry("400x500")
        favorites_window.configure(bg='#2c3e50')

        title_frame = tk.Frame(favorites_window, bg='#2c3e50')
        title_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(title_frame, text="⭐ Favori Kanallarım", font=('Arial', 12, 'bold'),
                 bg='#2c3e50', fg='white').pack()

        list_frame = tk.Frame(favorites_window, bg='#34495e')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(list_frame, bg='#2c3e50', fg='white',
                             selectbackground='#3498db', yscrollcommand=scrollbar.set)
        listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)

        for fav_id in self.favorites:
            name = fav_id.split('|')[0]
            group = fav_id.split('|')[2]
            listbox.insert(tk.END, f"{name} | {group}")

        def play_favorite(event):
            selection = listbox.curselection()
            if selection:
                fav_id = self.favorites[selection[0]]
                for playlist_name, playlist_data in self.playlists.items():
                    for channel in playlist_data['channels']:
                        if self.get_channel_id(channel) == fav_id:
                            self.play_channel(channel)
                            favorites_window.destroy()
                            return

        listbox.bind('<Double-Button-1>', play_favorite)

        btn_frame = tk.Frame(favorites_window, bg='#2c3e50')
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Button(btn_frame, text="❌ Kapat", command=favorites_window.destroy,
                  bg='#e74c3c', fg='white').pack(side=tk.RIGHT)

    def show_settings(self):
        messagebox.showinfo("Ayarlar", "Ayarlar penceresi geliştirme aşamasındadır.")

    def show_appearance_settings(self):
        messagebox.showinfo("Görünüm Ayarları", "Görünüm ayarları geliştirme aşamasındadır.")

    def show_playback_settings(self):
        messagebox.showinfo("Oynatma Ayarları", "Oynatma ayarları geliştirme aşamasındadır.")

    def show_help(self):
        help_text = """
🎯 Gelişmiş IPTV Player - Kullanım Kılavuzu

📥 PLAYLIST EKLEME:
• 🌐 URL Ekle: M3U URL'si ile playlist ekleyin
• 📁 Dosya Ekle: Bilgisayarınızdan M3U dosyası seçin
• ⚡ Xtreme Ekle: Xtreme Codes formatında playlist ekleyin

🎮 KONTROLLER:
• Çift tıklama: Kanalı oynat / Tam ekran
• F11: Tam ekran aç/kapat
• Sol kenar: Playlist panelini göster
• Alt kenar: Kontrolleri göster
• Sağ tık: İşlem menüsü

⭐ FAVORİLER:
• ⭐ butonu: Favorilere ekle/çıkar
• Sağ tık menüsü: Favori işlemleri
• Ctrl+F: Favori kanalları göster

⚡ XTREME CODES:
• Xtreme Codes formatını destekler
• Özel işaret (⚡) ile gösterilir
• Normal M3U gibi yönetilir

🔧 OYNATMA:
• ⏮️/⏭️: Kanal değiştir
• ⏪/⏩: 10 saniye atla
• 🔊: Ses kontrolü
• Aktif kanal mavi renkte gösterilir

📊 ÖZELLİKLER:
• Program üstünde oynatılan kanal bilgisi
• Otomatik playlist yükleme
• İlerleme çubuğu ve zaman göstergesi
• Grup bazlı kanal organizasyonu
        """
        messagebox.showinfo("Yardım", help_text)

    def show_about(self):
        messagebox.showinfo("Hakkında",
                            "Gelişmiş IPTV Player v3.0\n\n"
                            "Sürüm: 3.0\n"
                            "Geliştirici: Samim ÖZCOŞAR"
                            "Özellikler: M3U desteği, Xtreme Codes, favoriler, tam ekran, ilerleme çubuğu")

    def search_channels(self):
        search_term = simpledialog.askstring("Kanal Arama", "Aranacak kanal adını girin:")
        if search_term:
            results = []
            for playlist_name, playlist_data in self.playlists.items():
                for channel in playlist_data['channels']:
                    if search_term.lower() in channel['name'].lower():
                        results.append(f"{playlist_name} - {channel['name']} ({channel['group']})")

            if results:
                result_text = "\n".join(results[:20])  # İlk 20 sonuç
                if len(results) > 20:
                    result_text += f"\n\n... ve {len(results) - 20} daha fazla sonuç"
                messagebox.showinfo("Arama Sonuçları", f"Bulunan kanallar:\n\n{result_text}")
            else:
                messagebox.showinfo("Arama Sonuçları", "Kanal bulunamadı.")

    def update_all_playlists(self):
        count = 0
        for playlist_name, playlist_info in self.playlists.items():
            if 'url' in playlist_info and playlist_info['url']:
                threading.Thread(target=self.download_playlist,
                                 args=(playlist_info['url'], playlist_name, playlist_info.get('is_xtreme', False)),
                                 daemon=True).start()
                count += 1

        if count > 0:
            messagebox.showinfo("Güncelleme", f"{count} playlist güncelleniyor...")
        else:
            messagebox.showinfo("Güncelleme", "Güncellenecek playlist bulunamadı.")

    def show_stats(self):
        total_playlists = len(self.playlists)
        total_channels = sum(len(data['channels']) for data in self.playlists.values())
        total_groups = sum(len(data['groups']) for data in self.playlists.values())
        total_favorites = len(self.favorites)

        xtreme_count = sum(1 for data in self.playlists.values() if data.get('is_xtreme', False))

        stats_text = f"""
📊 İstatistikler:

📁 Toplam Playlist: {total_playlists}
  • Normal: {total_playlists - xtreme_count}
  • Xtreme: {xtreme_count}

📺 Toplam Kanal: {total_channels}
📂 Toplam Grup: {total_groups}
⭐ Favori Kanal: {total_favorites}

🎯 Aktif Kanal: {self.current_channel['name'] if self.current_channel else 'Yok'}
        """
        messagebox.showinfo("İstatistikler", stats_text)

    def show_playlist_stats(self, listbox):
        selection = listbox.curselection()
        if selection:
            name_with_badge = listbox.get(selection[0])
            name = name_with_badge.replace(" ⚡", "")
            playlist_info = self.playlists.get(name)

            if playlist_info:
                stats_text = f"""
📊 {name} İstatistikleri:

📺 Kanal Sayısı: {len(playlist_info['channels'])}
📂 Grup Sayısı: {len(playlist_info['groups'])}
🔗 Tip: {'Xtreme Codes ⚡' if playlist_info.get('is_xtreme', False) else 'Normal M3U'}
📝 Dosya: {os.path.basename(playlist_info['file_path'])}

📈 En Büyük Gruplar:
"""
                # Grup bazlı istatistikler
                group_stats = {}
                for channel in playlist_info['channels']:
                    group = channel['group']
                    group_stats[group] = group_stats.get(group, 0) + 1

                # En büyük 5 grup
                sorted_groups = sorted(group_stats.items(), key=lambda x: x[1], reverse=True)[:5]
                for group, count in sorted_groups:
                    stats_text += f"  • {group}: {count} kanal\n"

                messagebox.showinfo("Playlist İstatistikleri", stats_text)

    def reset_ui(self):
        """UI'ı sıfırla"""
        self.root.geometry("1200x700")
        self.show_left_frame()
        self.show_controls()
        if self.fullscreen:
            self.toggle_fullscreen()

    def update_selected_playlist(self, listbox):
        selection = listbox.curselection()
        if selection:
            name_with_badge = listbox.get(selection[0])
            name = name_with_badge.replace(" ⚡", "")
            playlist_info = self.playlists[name]

            if 'url' in playlist_info and playlist_info['url']:
                threading.Thread(
                    target=self.download_playlist,
                    args=(playlist_info['url'], name, playlist_info.get('is_xtreme', False)),
                    daemon=True
                ).start()
                messagebox.showinfo("Güncelleme", f"'{name}' playlist'i güncelleniyor...")
            else:
                messagebox.showinfo("Bilgi", "Bu playlist için güncelleme URL'si bulunamadı.")

    def delete_playlist(self, listbox):
        selection = listbox.curselection()
        if selection:
            name_with_badge = listbox.get(selection[0])
            name = name_with_badge.replace(" ⚡", "")

            result = messagebox.askyesno("Onay",
                                         f"'{name}' playlist'ini silmek istediğinizden emin misiniz?")
            if result:
                playlist_info = self.playlists.get(name)
                if playlist_info and 'file_path' in playlist_info:
                    file_path = playlist_info['file_path']
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            print(f"Dosya silinemedi: {e}")

                if name in self.playlists:
                    del self.playlists[name]

                listbox.delete(selection[0])
                self.update_playlist_listbox()

                messagebox.showinfo("Başarılı", "Playlist silindi.")


def main():
    root = tk.Tk()
    app = IPTVPlayer(root)
    root.mainloop()


if __name__ == "__main__":
    main()