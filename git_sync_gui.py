import wx
import os
import json
import subprocess
import shutil

# --- パスの動的取得と設定ファイルの位置 ---
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.expanduser("~/.kicad_lib_sync.json")
ICON_FILE = os.path.join(PLUGIN_DIR, "icon.png")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {"repositories": [], "local_libs": []}
    return {"repositories": [], "local_libs": []}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def get_project_dir():
    try:
        import pcbnew
        board = pcbnew.GetBoard()
        if board:
            board_path = board.GetFileName()
            if board_path:
                return os.path.dirname(board_path)
    except Exception:
        pass
    return None

def register_to_project_table(table_path, lib_name, rel_lib_uri, is_fp=False):
    if not os.path.exists(table_path):
        header = "(fp_lib_table)\n" if is_fp else "(sym_lib_table)\n"
        with open(table_path, 'w', encoding='utf-8') as f:
            f.write(header)

    with open(table_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()

    if f'name "{lib_name}"' in content or f'"{rel_lib_uri}"' in content:
        return f"[SKIP] Already in table: {lib_name}"

    shutil.copy2(table_path, table_path + ".bak")
    
    new_entry = f'  (lib (name "{lib_name}")(type "KiCad")(uri "{rel_lib_uri}")(options "")(descr ""))\n'

    if content.endswith(')'):
        content = content[:-1] + new_entry + ")"
    else:
        content = content + "\n" + new_entry

    with open(table_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return f"[ADDED] Registered: {lib_name}"


class GitLibSyncDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="KiCad Library Unified Manager", size=(800, 550), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        
        if os.path.exists(ICON_FILE):
            icon = wx.Icon(ICON_FILE, wx.BITMAP_TYPE_ANY)
            self.SetIcon(icon)

        self.config = load_config()
        self.config.setdefault("local_libs", [])

        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        
        self.notebook = wx.Notebook(self)
        self.git_panel = wx.Panel(self.notebook)
        self.local_panel = wx.Panel(self.notebook)
        
        self.notebook.AddPage(self.git_panel, "🌐 Git Repositories Sync")
        self.notebook.AddPage(self.local_panel, "📁 Local Libraries Import")

        self.init_git_panel()
        self.init_local_panel()

        dialog_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)
        self.SetSizer(dialog_sizer)

        self.refresh_git_list()
        self.refresh_local_list()

    # ==========================================
    # 1. Git Repositories Tab
    # ==========================================
    def init_git_panel(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        list_label = wx.StaticText(self.git_panel, label="Registered Repositories  (☑: Sync Target, [C]:Copy to Proj, [R]:Auto-Register):")
        main_sizer.Add(list_label, 0, wx.ALL, 5)

        self.git_listbox = wx.CheckListBox(self.git_panel, style=wx.LB_SINGLE)
        self.git_listbox.Bind(wx.EVT_LISTBOX, self.on_git_list_select)
        self.git_listbox.Bind(wx.EVT_CHECKLISTBOX, self.on_git_list_check)
        main_sizer.Add(self.git_listbox, 1, wx.EXPAND | wx.ALL, 5)

        input_sizer = wx.FlexGridSizer(rows=2, cols=2, vgap=5, hgap=5)
        input_sizer.AddGrowableCol(1, 1)

        input_sizer.Add(wx.StaticText(self.git_panel, label="Git URL:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.git_url_input = wx.TextCtrl(self.git_panel)
        input_sizer.Add(self.git_url_input, 1, wx.EXPAND)

        input_sizer.Add(wx.StaticText(self.git_panel, label="Local Dir:"), 0, wx.ALIGN_CENTER_VERTICAL)
        dir_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.git_dir_input = wx.TextCtrl(self.git_panel)
        self.git_dir_btn = wx.Button(self.git_panel, label="Browse...")
        self.git_dir_btn.Bind(wx.EVT_BUTTON, self.on_git_browse)
        dir_sizer.Add(self.git_dir_input, 1, wx.EXPAND | wx.RIGHT, 5)
        dir_sizer.Add(self.git_dir_btn, 0)
        
        input_sizer.Add(dir_sizer, 1, wx.EXPAND)
        main_sizer.Add(input_sizer, 0, wx.EXPAND | wx.ALL, 5)

        opt_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.git_chk_copy = wx.CheckBox(self.git_panel, label="Copy to project [C]")
        self.git_chk_reg = wx.CheckBox(self.git_panel, label="Register to table [R]")
        self.git_chk_copy.Bind(wx.EVT_CHECKBOX, self.on_git_checkbox_toggle)
        self.git_chk_reg.Bind(wx.EVT_CHECKBOX, self.on_git_checkbox_toggle)
        
        opt_sizer.Add(self.git_chk_copy, 0, wx.RIGHT, 15)
        opt_sizer.Add(self.git_chk_reg, 0)
        main_sizer.Add(opt_sizer, 0, wx.ALL, 5)

        manage_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.git_add_btn = wx.Button(self.git_panel, label="Add New")
        self.git_update_btn = wx.Button(self.git_panel, label="Update Selected URL/Dir")
        self.git_remove_btn = wx.Button(self.git_panel, label="Remove Selected")
        
        self.git_add_btn.Bind(wx.EVT_BUTTON, self.on_git_add)
        self.git_update_btn.Bind(wx.EVT_BUTTON, self.on_git_update)
        self.git_remove_btn.Bind(wx.EVT_BUTTON, self.on_git_remove)
        
        manage_btn_sizer.Add(self.git_add_btn, 0, wx.RIGHT, 5)
        manage_btn_sizer.Add(self.git_update_btn, 0, wx.RIGHT, 5)
        manage_btn_sizer.Add(self.git_remove_btn, 0)
        main_sizer.Add(manage_btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        main_sizer.Add(wx.StaticLine(self.git_panel), 0, wx.EXPAND | wx.ALL, 5)

        action_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.git_sync_btn = wx.Button(self.git_panel, label="Sync All Checked Operations")
        self.git_close_btn = wx.Button(self.git_panel, label="Close")
        self.git_sync_btn.Bind(wx.EVT_BUTTON, self.on_git_sync)
        self.git_close_btn.Bind(wx.EVT_BUTTON, self.on_close)
        
        action_btn_sizer.Add(self.git_sync_btn, 1, wx.EXPAND | wx.RIGHT, 5)
        action_btn_sizer.Add(self.git_close_btn, 0, wx.EXPAND)
        main_sizer.Add(action_btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.git_panel.SetSizer(main_sizer)

    def refresh_git_list(self):
        self.git_listbox.Clear()
        for i, repo in enumerate(self.config.get("repositories", [])):
            c_mark = "C" if repo.get("copy", False) else " "
            r_mark = "R" if repo.get("reg", False) else " "
            display_str = f"[{c_mark}][{r_mark}]  {repo['url']}  ->  {repo['dir']}"
            self.git_listbox.Append(display_str)
            self.git_listbox.Check(i, repo.get("sync", True))

    def on_git_list_select(self, event):
        selection = self.git_listbox.GetSelection()
        if selection != wx.NOT_FOUND:
            repo = self.config.get("repositories", [])[selection]
            self.git_url_input.SetValue(repo.get("url", ""))
            self.git_dir_input.SetValue(repo.get("dir", ""))
            self.git_chk_copy.SetValue(repo.get("copy", False))
            self.git_chk_reg.SetValue(repo.get("reg", False))

    def on_git_list_check(self, event):
        index = event.GetInt()
        repos = self.config.get("repositories", [])
        if 0 <= index < len(repos):
            repos[index]["sync"] = self.git_listbox.IsChecked(index)
            try: save_config(self.config)
            except Exception: pass

    def on_git_checkbox_toggle(self, event):
        selection = self.git_listbox.GetSelection()
        if selection != wx.NOT_FOUND:
            repos = self.config.get("repositories", [])
            repos[selection]["copy"] = self.git_chk_copy.GetValue()
            repos[selection]["reg"] = self.git_chk_reg.GetValue()
            try: save_config(self.config)
            except Exception: pass
            self.refresh_git_list()
            self.git_listbox.SetSelection(selection)

    def on_git_browse(self, event):
        with wx.DirDialog(self, "Choose destination directory", style=wx.DD_DEFAULT_STYLE) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.git_dir_input.SetValue(dlg.GetPath())

    def on_git_add(self, event):
        url = self.git_url_input.GetValue().strip()
        directory = self.git_dir_input.GetValue().strip()
        if not url or not directory:
            wx.MessageBox("Both Git URL and Local Directory are required.", "Input Error", wx.ICON_WARNING)
            return
        repos = self.config.setdefault("repositories", [])
        if any(r['url'] == url for r in repos):
            wx.MessageBox("This repository URL is already registered.", "Duplicate Error", wx.ICON_WARNING)
            return
        repos.append({
            "url": url, "dir": directory, "sync": True,
            "copy": self.git_chk_copy.GetValue(), "reg": self.git_chk_reg.GetValue()
        })
        try: save_config(self.config)
        except Exception: pass
        self.refresh_git_list()
        self.git_listbox.SetSelection(len(repos) - 1)

    def on_git_update(self, event):
        selection = self.git_listbox.GetSelection()
        if selection == wx.NOT_FOUND: return
        url = self.git_url_input.GetValue().strip()
        directory = self.git_dir_input.GetValue().strip()
        repos = self.config.get("repositories", [])
        repos[selection]["url"] = url
        repos[selection]["dir"] = directory
        try: save_config(self.config)
        except Exception: pass
        self.refresh_git_list()
        self.git_listbox.SetSelection(selection)

    def on_git_remove(self, event):
        selection = self.git_listbox.GetSelection()
        if selection == wx.NOT_FOUND: return
        repos = self.config.get("repositories", [])
        del repos[selection]
        try: save_config(self.config)
        except Exception: pass
        self.git_url_input.Clear()
        self.git_dir_input.Clear()
        self.refresh_git_list()

    def on_git_sync(self, event):
        repos = self.config.get("repositories", [])
        target_repos = [repo for repo in repos if repo.get("sync", True)]
        if not target_repos:
            wx.MessageBox("No repositories are checked for sync.", "Info", wx.ICON_INFORMATION)
            return
        project_dir = get_project_dir()
        results = []
        success_count = 0

        progress = wx.ProgressDialog("Syncing Repositories", "Starting sync...", maximum=len(target_repos), parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)

        for i, repo in enumerate(target_repos):
            url = repo.get("url")
            target_dir = os.path.expanduser(repo.get("dir")).replace('\\', '/')
            do_copy = repo.get("copy", False)
            do_reg = repo.get("reg", False)
            progress.Update(i, f"Processing: {url}")
            git_dir = os.path.join(target_dir, ".git")
            sync_ok = False

            if os.path.exists(git_dir):
                res = subprocess.run(["git", "-C", target_dir, "pull"], capture_output=True, text=True)
                if res.returncode == 0: sync_ok = True
                else: results.append(f"[FAIL] Pull: {url}\n  {res.stderr.strip()}")
            else:
                if os.path.exists(target_dir) and os.listdir(target_dir):
                    results.append(f"[FAIL] Clone: {url}\n  Directory not empty: {target_dir}")
                else:
                    os.makedirs(target_dir, exist_ok=True)
                    res = subprocess.run(["git", "clone", url, target_dir], capture_output=True, text=True)
                    if res.returncode == 0: sync_ok = True
                    else: results.append(f"[FAIL] Clone: {url}\n  {res.stderr.strip()}")

            if not sync_ok: continue
            success_count += 1
            log_msgs = [f"[OK] Git Synced: {url}"]

            if do_copy or do_reg:
                if not project_dir:
                    log_msgs.append("  -> [SKIP] Cannot detect current KiCad project.")
                else:
                    repo_basename = os.path.basename(target_dir.rstrip('/')) or "unnamed_repo"
                    proj_libs_dir = os.path.join(project_dir, "local_git_libs", repo_basename)
                    
                    if do_copy:
                        try:
                            shutil.copytree(target_dir, proj_libs_dir, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.git'))
                            log_msgs.append(f"  -> [OK] Copied to: local_git_libs/{repo_basename}")
                        except Exception as e:
                            log_msgs.append(f"  -> [FAIL] Copy failed: {e}")
                            do_reg = False 
                    
                    if do_reg:
                        sym_table = os.path.join(project_dir, "sym-lib-table")
                        fp_table = os.path.join(project_dir, "fp-lib-table")
                        reg_logs = []
                        scan_dir = proj_libs_dir if do_copy else target_dir
                        for root, dirs, files in os.walk(scan_dir):
                            for file in files:
                                if file.endswith(".kicad_sym"):
                                    lib_name = os.path.splitext(file)[0]
                                    full_path = os.path.join(root, file).replace("\\", "/")
                                    rel_path = os.path.relpath(full_path, project_dir).replace("\\", "/")
                                    uri = f"${{KIPRJMOD}}/{rel_path}"
                                    reg_logs.append("    " + register_to_project_table(sym_table, lib_name, uri, is_fp=False))
                            for d in dirs:
                                if d.endswith(".pretty"):
                                    lib_name = os.path.splitext(d)[0]
                                    full_path = os.path.join(root, d).replace("\\", "/")
                                    rel_path = os.path.relpath(full_path, project_dir).replace("\\", "/")
                                    uri = f"${{KIPRJMOD}}/{rel_path}"
                                    reg_logs.append("    " + register_to_project_table(fp_table, lib_name, uri, is_fp=True))
                        if reg_logs:
                            log_msgs.append("  -> Auto-Registration:")
                            log_msgs.extend(reg_logs)
            results.append("\n".join(log_msgs))

        progress.Destroy()
        summary = f"Completed: {success_count} / {len(target_repos)} targets synced successfully.\n\n" + "\n\n".join(results)
        wx.MessageBox(summary, "Result Summary", wx.ICON_INFORMATION)


    # ==========================================
    # 2. Local Libraries Tab (拡張版)
    # ==========================================
    def init_local_panel(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        list_label = wx.StaticText(self.local_panel, label="Registered Local Sources (☑: Target, [C]:Copy, [R]:Register):")
        main_sizer.Add(list_label, 0, wx.ALL, 5)

        self.local_listbox = wx.CheckListBox(self.local_panel, style=wx.LB_SINGLE)
        self.local_listbox.Bind(wx.EVT_LISTBOX, self.on_local_list_select)
        self.local_listbox.Bind(wx.EVT_CHECKLISTBOX, self.on_local_list_check)
        main_sizer.Add(self.local_listbox, 1, wx.EXPAND | wx.ALL, 5)

        input_sizer = wx.FlexGridSizer(rows=1, cols=2, vgap=5, hgap=5)
        input_sizer.AddGrowableCol(1, 1)

        input_sizer.Add(wx.StaticText(self.local_panel, label="Source Path:"), 0, wx.ALIGN_CENTER_VERTICAL)
        
        path_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.local_path_input = wx.TextCtrl(self.local_panel)
        self.local_file_btn = wx.Button(self.local_panel, label="Browse File...")
        self.local_dir_btn = wx.Button(self.local_panel, label="Browse Folder...")
        
        self.local_file_btn.Bind(wx.EVT_BUTTON, self.on_local_browse_file)
        self.local_dir_btn.Bind(wx.EVT_BUTTON, self.on_local_browse_dir)
        
        path_sizer.Add(self.local_path_input, 1, wx.EXPAND | wx.RIGHT, 5)
        path_sizer.Add(self.local_file_btn, 0, wx.RIGHT, 5)
        path_sizer.Add(self.local_dir_btn, 0)
        
        input_sizer.Add(path_sizer, 1, wx.EXPAND)
        main_sizer.Add(input_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # --- 新規追加: LocalタブにもCとRのチェックボックスを設置 ---
        opt_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.local_chk_copy = wx.CheckBox(self.local_panel, label="Copy to project [C]")
        self.local_chk_reg = wx.CheckBox(self.local_panel, label="Register to table [R]")
        self.local_chk_copy.Bind(wx.EVT_CHECKBOX, self.on_local_checkbox_toggle)
        self.local_chk_reg.Bind(wx.EVT_CHECKBOX, self.on_local_checkbox_toggle)
        
        opt_sizer.Add(self.local_chk_copy, 0, wx.RIGHT, 15)
        opt_sizer.Add(self.local_chk_reg, 0)
        main_sizer.Add(opt_sizer, 0, wx.ALL, 5)

        manage_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.local_add_btn = wx.Button(self.local_panel, label="Add New")
        self.local_update_btn = wx.Button(self.local_panel, label="Update Selected")
        self.local_remove_btn = wx.Button(self.local_panel, label="Remove Selected")
        
        self.local_add_btn.Bind(wx.EVT_BUTTON, self.on_local_add)
        self.local_update_btn.Bind(wx.EVT_BUTTON, self.on_local_update)
        self.local_remove_btn.Bind(wx.EVT_BUTTON, self.on_local_remove)
        
        manage_btn_sizer.Add(self.local_add_btn, 0, wx.RIGHT, 5)
        manage_btn_sizer.Add(self.local_update_btn, 0, wx.RIGHT, 5)
        manage_btn_sizer.Add(self.local_remove_btn, 0)
        main_sizer.Add(manage_btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        main_sizer.Add(wx.StaticLine(self.local_panel), 0, wx.EXPAND | wx.ALL, 5)

        action_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.local_sync_btn = wx.Button(self.local_panel, label="Process Checked Operations")
        self.local_close_btn = wx.Button(self.local_panel, label="Close")
        
        self.local_sync_btn.Bind(wx.EVT_BUTTON, self.on_local_sync)
        self.local_close_btn.Bind(wx.EVT_BUTTON, self.on_close)
        
        action_btn_sizer.Add(self.local_sync_btn, 1, wx.EXPAND | wx.RIGHT, 5)
        action_btn_sizer.Add(self.local_close_btn, 0, wx.EXPAND)
        main_sizer.Add(action_btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.local_panel.SetSizer(main_sizer)

    def refresh_local_list(self):
        self.local_listbox.Clear()
        for i, lib in enumerate(self.config.get("local_libs", [])):
            c_mark = "C" if lib.get("copy", False) else " "
            r_mark = "R" if lib.get("reg", False) else " "
            display_str = f"[{c_mark}][{r_mark}]  {lib.get('path', '')}"
            self.local_listbox.Append(display_str)
            self.local_listbox.Check(i, lib.get("sync", True))

    def on_local_list_select(self, event):
        selection = self.local_listbox.GetSelection()
        if selection != wx.NOT_FOUND:
            lib = self.config.get("local_libs", [])[selection]
            self.local_path_input.SetValue(lib.get("path", ""))
            self.local_chk_copy.SetValue(lib.get("copy", False))
            self.local_chk_reg.SetValue(lib.get("reg", False))

    def on_local_list_check(self, event):
        index = event.GetInt()
        libs = self.config.get("local_libs", [])
        if 0 <= index < len(libs):
            libs[index]["sync"] = self.local_listbox.IsChecked(index)
            try: save_config(self.config)
            except Exception: pass

    def on_local_checkbox_toggle(self, event):
        selection = self.local_listbox.GetSelection()
        if selection != wx.NOT_FOUND:
            libs = self.config.get("local_libs", [])
            libs[selection]["copy"] = self.local_chk_copy.GetValue()
            libs[selection]["reg"] = self.local_chk_reg.GetValue()
            try: save_config(self.config)
            except Exception: pass
            self.refresh_local_list()
            self.local_listbox.SetSelection(selection)

    def on_local_browse_file(self, event):
        with wx.FileDialog(self, "Choose KiCad Symbol file", wildcard="KiCad Symbol (*.kicad_sym)|*.kicad_sym|All files (*.*)|*.*", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.local_path_input.SetValue(dlg.GetPath())

    def on_local_browse_dir(self, event):
        with wx.DirDialog(self, "Choose Library Folder", style=wx.DD_DEFAULT_STYLE) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.local_path_input.SetValue(dlg.GetPath())

    def on_local_add(self, event):
        path = self.local_path_input.GetValue().strip()
        if not path:
            wx.MessageBox("Source path is required.", "Input Error", wx.ICON_WARNING)
            return
        libs = self.config.setdefault("local_libs", [])
        if any(l['path'] == path for l in libs):
            wx.MessageBox("This path is already registered.", "Duplicate", wx.ICON_WARNING)
            return
        libs.append({
            "path": path, 
            "sync": True,
            "copy": self.local_chk_copy.GetValue(),
            "reg": self.local_chk_reg.GetValue()
        })
        try: save_config(self.config)
        except Exception: pass
        self.refresh_local_list()
        self.local_listbox.SetSelection(len(libs) - 1)

    def on_local_update(self, event):
        selection = self.local_listbox.GetSelection()
        if selection == wx.NOT_FOUND: return
        path = self.local_path_input.GetValue().strip()
        libs = self.config.get("local_libs", [])
        libs[selection]["path"] = path
        try: save_config(self.config)
        except Exception: pass
        self.refresh_local_list()
        self.local_listbox.SetSelection(selection)

    def on_local_remove(self, event):
        selection = self.local_listbox.GetSelection()
        if selection == wx.NOT_FOUND: return
        libs = self.config.get("local_libs", [])
        del libs[selection]
        try: save_config(self.config)
        except Exception: pass
        self.local_path_input.Clear()
        self.refresh_local_list()

    def on_local_sync(self, event):
        libs = self.config.get("local_libs", [])
        target_libs = [lib for lib in libs if lib.get("sync", True)]
        
        if not target_libs:
            wx.MessageBox("No local libraries are checked for import/registration.", "Info", wx.ICON_INFORMATION)
            return

        project_dir = get_project_dir()
        if not project_dir:
            wx.MessageBox("Cannot detect current KiCad project. Open and save a PCB file first.", "Project Not Found", wx.ICON_ERROR)
            return

        results = []
        success_count = 0
        progress = wx.ProgressDialog("Processing Libraries", "Starting...", maximum=len(target_libs), parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)

        for i, lib in enumerate(target_libs):
            src_path = os.path.expanduser(lib.get("path")).replace('\\', '/')
            do_copy = lib.get("copy", False)
            do_reg = lib.get("reg", False)
            
            progress.Update(i, f"Processing: {src_path}")
            
            if not do_copy and not do_reg:
                results.append(f"[SKIP] No action (C/R) selected for: {src_path}")
                continue
                
            if not os.path.exists(src_path):
                results.append(f"[FAIL] Path not found: {src_path}")
                continue

            sym_table = os.path.join(project_dir, "sym-lib-table")
            fp_table = os.path.join(project_dir, "fp-lib-table")
            reg_logs = []
            
            scan_dir = src_path
            use_kiprjmod = False
            
            try:
                # --- コピー処理 ---
                if do_copy:
                    target_dir = os.path.join(project_dir, "local_imported_libs")
                    os.makedirs(target_dir, exist_ok=True)
                    
                    if os.path.isfile(src_path):
                        shutil.copy2(src_path, target_dir)
                        scan_dir = os.path.join(target_dir, os.path.basename(src_path)).replace('\\', '/')
                    else:
                        basename = os.path.basename(src_path.rstrip('/')) or "lib_folder"
                        dest_folder = os.path.join(target_dir, basename).replace('\\', '/')
                        shutil.copytree(src_path, dest_folder, dirs_exist_ok=True)
                        scan_dir = dest_folder
                    use_kiprjmod = True

                # --- 登録処理 ---
                if do_reg:
                    # 1. 単一のシンボルファイルが指定された場合
                    if os.path.isfile(scan_dir) and scan_dir.endswith(".kicad_sym"):
                        lib_name = os.path.splitext(os.path.basename(scan_dir))[0]
                        if use_kiprjmod:
                            rel_path = os.path.relpath(scan_dir, project_dir).replace("\\", "/")
                            uri = f"${{KIPRJMOD}}/{rel_path}"
                        else:
                            uri = scan_dir  # コピーしない場合は絶対パスを直接登録
                        reg_logs.append("  -> " + register_to_project_table(sym_table, lib_name, uri, is_fp=False))
                    
                    # 2. .prettyフォルダ自体が指定された場合
                    elif os.path.isdir(scan_dir) and scan_dir.endswith(".pretty"):
                        lib_name = os.path.splitext(os.path.basename(scan_dir))[0]
                        if use_kiprjmod:
                            rel_path = os.path.relpath(scan_dir, project_dir).replace("\\", "/")
                            uri = f"${{KIPRJMOD}}/{rel_path}"
                        else:
                            uri = scan_dir
                        reg_logs.append("  -> " + register_to_project_table(fp_table, lib_name, uri, is_fp=True))
                    
                    # 3. 複数のライブラリを含む大元のフォルダが指定された場合
                    elif os.path.isdir(scan_dir):
                        for root, dirs, files in os.walk(scan_dir):
                            for file in files:
                                if file.endswith(".kicad_sym"):
                                    lib_name = os.path.splitext(file)[0]
                                    full_path = os.path.join(root, file).replace("\\", "/")
                                    if use_kiprjmod:
                                        rel_path = os.path.relpath(full_path, project_dir).replace("\\", "/")
                                        uri = f"${{KIPRJMOD}}/{rel_path}"
                                    else:
                                        uri = full_path
                                    reg_logs.append("  -> " + register_to_project_table(sym_table, lib_name, uri, is_fp=False))
                            for d in dirs:
                                if d.endswith(".pretty"):
                                    lib_name = os.path.splitext(d)[0]
                                    full_path = os.path.join(root, d).replace("\\", "/")
                                    if use_kiprjmod:
                                        rel_path = os.path.relpath(full_path, project_dir).replace("\\", "/")
                                        uri = f"${{KIPRJMOD}}/{rel_path}"
                                    else:
                                        uri = full_path
                                    reg_logs.append("  -> " + register_to_project_table(fp_table, lib_name, uri, is_fp=True))

                success_count += 1
                log_msgs = [f"[OK] Processed: {src_path}"]
                if do_copy:
                    log_msgs.append(f"  -> Copied to local_imported_libs")
                if reg_logs:
                    log_msgs.extend(reg_logs)
                elif do_reg:
                    log_msgs.append("  -> [SKIP] No .kicad_sym or .pretty found to register.")
                
                results.append("\n".join(log_msgs))
                
            except Exception as e:
                results.append(f"[FAIL] Error processing {src_path}:\n  {e}")

        progress.Destroy()
        summary = f"Completed: {success_count} / {len(target_libs)} sources processed successfully.\n\n" + "\n\n".join(results)
        wx.MessageBox(summary, "Processing Summary", wx.ICON_INFORMATION)

    # ==========================================
    # 共通関数
    # ==========================================
    def on_close(self, event):
        self.EndModal(wx.ID_OK)


try:
    import pcbnew
    HAS_PCBNEW = True
except ImportError:
    HAS_PCBNEW = False

if HAS_PCBNEW:
    class GitLibSyncGUIPlugin(pcbnew.ActionPlugin):
        def defaults(self):
            self.name = "KiCad Library Unified Manager"
            self.category = "Utility"
            self.description = "Unified GUI to manage Git repositories and local libraries."
            self.show_toolbar_button = True
            if os.path.exists(ICON_FILE):
                self.icon_file_name = ICON_FILE

        def Run(self):
            top_window = wx.GetTopLevelWindows()[0]
            dlg = GitLibSyncDialog(top_window)
            dlg.ShowModal()
            dlg.Destroy()

    GitLibSyncGUIPlugin().register()

if __name__ == "__main__":
    app = wx.App(False)
    dlg = GitLibSyncDialog(None)
    dlg.ShowModal()
    dlg.Destroy()