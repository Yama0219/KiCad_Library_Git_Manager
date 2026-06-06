import wx
import os
import json
import subprocess
import shutil

# --- パスの動的取得と設定ファイルの位置 ---
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
# JSONはユーザーのホームディレクトリに保存（安全性のため元に戻しました）
CONFIG_FILE = os.path.expanduser("~/.kicad_lib_sync.json")
# アイコンはプラグインフォルダ内を参照
ICON_FILE = os.path.join(PLUGIN_DIR, "icon.png")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {"repositories": []}
    return {"repositories": []}

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
        return f"[SKIP] Already in project table: {lib_name}"

    shutil.copy2(table_path, table_path + ".bak")
    
    new_entry = f'  (lib (name "{lib_name}")(type "KiCad")(uri "{rel_lib_uri}")(options "")(descr ""))\n'

    if content.endswith(')'):
        content = content[:-1] + new_entry + ")"
    else:
        content = content + "\n" + new_entry

    with open(table_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return f"[ADDED] Project table: {lib_name}"

class GitLibSyncDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Git Library Sync Manager", size=(700, 500), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        
        if os.path.exists(ICON_FILE):
            icon = wx.Icon(ICON_FILE, wx.BITMAP_TYPE_ANY)
            self.SetIcon(icon)

        self.config = load_config()

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        list_label = wx.StaticText(self, label="Registered Repositories  ([C]:Copy to Proj, [R]:Auto-Register):")
        main_sizer.Add(list_label, 0, wx.ALL, 5)

        self.repo_listbox = wx.ListBox(self, style=wx.LB_SINGLE)
        self.repo_listbox.Bind(wx.EVT_LISTBOX, self.on_list_select)
        main_sizer.Add(self.repo_listbox, 1, wx.EXPAND | wx.ALL, 5)

        input_sizer = wx.FlexGridSizer(rows=2, cols=2, vgap=5, hgap=5)
        input_sizer.AddGrowableCol(1, 1)

        input_sizer.Add(wx.StaticText(self, label="Git URL:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.url_input = wx.TextCtrl(self)
        input_sizer.Add(self.url_input, 1, wx.EXPAND)

        input_sizer.Add(wx.StaticText(self, label="Local Dir:"), 0, wx.ALIGN_CENTER_VERTICAL)
        dir_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.dir_input = wx.TextCtrl(self)
        self.dir_btn = wx.Button(self, label="Browse...")
        self.dir_btn.Bind(wx.EVT_BUTTON, self.on_browse)
        dir_sizer.Add(self.dir_input, 1, wx.EXPAND | wx.RIGHT, 5)
        dir_sizer.Add(self.dir_btn, 0)
        
        input_sizer.Add(dir_sizer, 1, wx.EXPAND)
        main_sizer.Add(input_sizer, 0, wx.EXPAND | wx.ALL, 5)

        opt_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.chk_copy = wx.CheckBox(self, label="Copy to current project folder")
        self.chk_reg = wx.CheckBox(self, label="Register to project library table")
        opt_sizer.Add(self.chk_copy, 0, wx.RIGHT, 15)
        opt_sizer.Add(self.chk_reg, 0)
        main_sizer.Add(opt_sizer, 0, wx.ALL, 5)

        manage_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.add_btn = wx.Button(self, label="Add New")
        self.update_btn = wx.Button(self, label="Update Selected")
        self.remove_btn = wx.Button(self, label="Remove Selected")
        
        self.add_btn.Bind(wx.EVT_BUTTON, self.on_add)
        self.update_btn.Bind(wx.EVT_BUTTON, self.on_update)
        self.remove_btn.Bind(wx.EVT_BUTTON, self.on_remove)
        
        manage_btn_sizer.Add(self.add_btn, 0, wx.RIGHT, 5)
        manage_btn_sizer.Add(self.update_btn, 0, wx.RIGHT, 5)
        manage_btn_sizer.Add(self.remove_btn, 0)
        main_sizer.Add(manage_btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        main_sizer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.ALL, 5)

        action_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sync_btn = wx.Button(self, label="Sync All Selected Operations")
        self.close_btn = wx.Button(self, label="Close")
        self.sync_btn.Bind(wx.EVT_BUTTON, self.on_sync)
        self.close_btn.Bind(wx.EVT_BUTTON, self.on_close)
        
        action_btn_sizer.Add(self.sync_btn, 1, wx.EXPAND | wx.RIGHT, 5)
        action_btn_sizer.Add(self.close_btn, 0, wx.EXPAND)
        main_sizer.Add(action_btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(main_sizer)
        self.refresh_list()

    def refresh_list(self):
        self.repo_listbox.Clear()
        for repo in self.config.get("repositories", []):
            c_mark = "C" if repo.get("copy", False) else " "
            r_mark = "R" if repo.get("reg", False) else " "
            display_str = f"[{c_mark}][{r_mark}]  {repo['url']}  ->  {repo['dir']}"
            self.repo_listbox.Append(display_str)

    def on_list_select(self, event):
        selection = self.repo_listbox.GetSelection()
        if selection != wx.NOT_FOUND:
            repo = self.config.get("repositories", [])[selection]
            self.url_input.SetValue(repo.get("url", ""))
            self.dir_input.SetValue(repo.get("dir", ""))
            self.chk_copy.SetValue(repo.get("copy", False))
            self.chk_reg.SetValue(repo.get("reg", False))

    def on_browse(self, event):
        with wx.DirDialog(self, "Choose destination directory", style=wx.DD_DEFAULT_STYLE) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.dir_input.SetValue(dlg.GetPath())

    def on_add(self, event):
        url = self.url_input.GetValue().strip()
        directory = self.dir_input.GetValue().strip()
        
        if not url or not directory:
            wx.MessageBox("Both Git URL and Local Directory are required.", "Input Error", wx.ICON_WARNING)
            return
            
        repos = self.config.setdefault("repositories", [])
        if any(r['url'] == url for r in repos):
            wx.MessageBox("This repository URL is already registered.", "Duplicate Error", wx.ICON_WARNING)
            return

        repos.append({
            "url": url, 
            "dir": directory,
            "copy": self.chk_copy.GetValue(),
            "reg": self.chk_reg.GetValue()
        })
        try:
            save_config(self.config)
        except Exception as e:
            wx.MessageBox(f"Failed to save config.\n{e}", "Save Error", wx.ICON_ERROR)
            return
            
        self.refresh_list()
        self.repo_listbox.SetSelection(len(repos) - 1)

    def on_update(self, event):
        selection = self.repo_listbox.GetSelection()
        if selection == wx.NOT_FOUND:
            wx.MessageBox("Please select a repository to update.", "Selection Error", wx.ICON_WARNING)
            return

        url = self.url_input.GetValue().strip()
        directory = self.dir_input.GetValue().strip()

        if not url or not directory:
            wx.MessageBox("Both Git URL and Local Directory are required.", "Input Error", wx.ICON_WARNING)
            return

        repos = self.config.get("repositories", [])
        if any(r['url'] == url for i, r in enumerate(repos) if i != selection):
            wx.MessageBox("This repository URL is already registered in another entry.", "Duplicate Error", wx.ICON_WARNING)
            return

        repos[selection] = {
            "url": url, 
            "dir": directory,
            "copy": self.chk_copy.GetValue(),
            "reg": self.chk_reg.GetValue()
        }
        try:
            save_config(self.config)
        except Exception as e:
            wx.MessageBox(f"Failed to save config.\n{e}", "Save Error", wx.ICON_ERROR)
            return
            
        self.refresh_list()
        self.repo_listbox.SetSelection(selection)

    def on_remove(self, event):
        selection = self.repo_listbox.GetSelection()
        if selection == wx.NOT_FOUND:
            wx.MessageBox("Please select a repository to remove.", "Selection Error", wx.ICON_WARNING)
            return
            
        repos = self.config.get("repositories", [])
        del repos[selection]
        try:
            save_config(self.config)
        except Exception as e:
            wx.MessageBox(f"Failed to save config.\n{e}", "Save Error", wx.ICON_ERROR)
            return
        
        self.url_input.Clear()
        self.dir_input.Clear()
        self.chk_copy.SetValue(False)
        self.chk_reg.SetValue(False)
        self.refresh_list()

    def on_sync(self, event):
        repos = self.config.get("repositories", [])
        if not repos:
            wx.MessageBox("No repositories to sync.", "Info", wx.ICON_INFORMATION)
            return

        project_dir = get_project_dir()
        
        results = []
        success_count = 0
        total_repos = len(repos)

        progress = wx.ProgressDialog("Syncing Repositories", "Starting sync...", maximum=total_repos, parent=self,
                                     style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)

        for i, repo in enumerate(repos):
            url = repo.get("url")
            target_dir = os.path.expanduser(repo.get("dir"))
            do_copy = repo.get("copy", False)
            do_reg = repo.get("reg", False)
            
            progress.Update(i, f"Processing: {url}")
            git_dir = os.path.join(target_dir, ".git")
            sync_ok = False

            if os.path.exists(git_dir):
                res = subprocess.run(["git", "-C", target_dir, "pull"], capture_output=True, text=True)
                if res.returncode == 0:
                    sync_ok = True
                else:
                    results.append(f"[FAIL] Pull: {url}\n  {res.stderr.strip()}")
            else:
                if os.path.exists(target_dir) and os.listdir(target_dir):
                    results.append(f"[FAIL] Clone: {url}\n  Directory not empty: {target_dir}")
                else:
                    os.makedirs(target_dir, exist_ok=True)
                    res = subprocess.run(["git", "clone", url, target_dir], capture_output=True, text=True)
                    if res.returncode == 0:
                        sync_ok = True
                    else:
                        results.append(f"[FAIL] Clone: {url}\n  {res.stderr.strip()}")

            if not sync_ok:
                continue
                
            success_count += 1
            log_msgs = [f"[OK] Git Synced: {url}"]

            if do_copy or do_reg:
                if not project_dir:
                    log_msgs.append("  -> [SKIP] Cannot detect current KiCad project.")
                else:
                    repo_basename = os.path.basename(target_dir.rstrip('/\\'))
                    if not repo_basename:
                        repo_basename = "unnamed_repo"
                        
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
        summary = f"Completed: {success_count} / {total_repos} successful.\n\n" + "\n\n".join(results)
        wx.MessageBox(summary, "Result Summary", wx.ICON_INFORMATION)

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
            self.name = "Git Library Sync Manager"
            self.category = "Utility"
            self.description = "Manage, sync, copy, and auto-register Git repositories to local project."
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