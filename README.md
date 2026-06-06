# KiCad_Library_Unified_Manager 

KiCadのシンボルおよびフットプリントライブラリをGitリポジトリ経由で管理する機能に加え、外部ツールでダウンロードしたローカルライブラリのプロジェクト取り込み・登録をワンクリックで行うためのKiCadアクションプラグイン。

## 内容
タブによる機能切り替え:
GUI上部のタブで「Git Repositories Sync」と「Local Libraries Import」を切り替えて操作。

【Git Repositories Sync（Git連携機能）】  
GUIベースの管理: KiCadのPCBエディタ上から、ダイアログでGitリポジトリ（URLとローカル保存先）の登録・更新・削除が可能。
Git同期: 登録された全リポジトリに対し、ローカルに存在しなければ git clone、存在すれば git pull を自動で判別して一括実行。
[S] Sync Target: 同期対象とするリポジトリをリストのチェックボックスで個別にオン/オフ可能。

【Local Libraries Import（ローカルライブラリ取り込み機能）】  
手軽なローカル管理: SamacSysやUltraLibrarianなどから取得したシンボル（.kicad_sym）やフットプリントフォルダ（.pretty）のパスを登録。

【プロジェクト・ローカル管理への登録（共通）】  
[C] Copy: 同期・指定したライブラリを、現在開いているKiCadプロジェクト内の local_git_libs/ または local_imported_libs/ フォルダへ自動コピー（Git連携時は容量削減のため .git 履歴データは除外）。
[R] Register: コピーされたライブラリをスキャンし、プロジェクト固有のライブラリテーブル（sym-lib-table, fp-lib-table）へ環境変数 ${KIPRJMOD} を用いた相対パスで自動登録。

## インストール方法 (Installation)
### 前提条件
* KiCad 8.0 以上（内部にwxPythonを含む環境）
* OSに Git がインストールされており、コマンドラインから git コマンドが実行可能であること。

### 導入手順
本ツールのフォルダ（例: git_lib_sync/）を、KiCadのグローバルプラグインディレクトリに配置する。

Windows: %USERPROFILE%\Documents\KiCad\{version}\scripting\plugins
macOS: ~/Library/Preferences/kicad/{version}/scripting/plugins
Linux: ~/.local/share/kicad/{version}/scripting/plugins

フォルダの構成が以下のようになっていることを確認する。

plugins/  
    ├─ git_sync_gui.py  
    └─ icon.png  

(※ 設定データは安全のため、プラグインフォルダ内ではなくユーザーのホームディレクトリ ~/.kicad_lib_sync.json に保存される。)

## 使い方 (Usage)
### 1. プラグインの起動
KiCadから: PCBエディタのツールバーアイコン、または上部メニュー「ツール」>「外部プラグイン」>「KiCad Library Unified Manager」をクリックする。

スタンドアロン起動: コマンドプロンプトやターミナルから以下を実行する。
```
python git_sync_gui.py
```

### 2. Gitリポジトリの登録と同期 (Git Repositories Sync タブ)
1. 画面下部の Git URL に対象のURLを入力（例: https://github.com/.../kicad-libs.git）、Local Dir にPC上での保存先ディレクトリを指定する。
2. 対象プロジェクトにデータを引き継ぎたい場合は、以下のオプションにチェックを入れる。
    * Copy to project [C]: 同期後、プロジェクトフォルダへコピーする。
    * Register to table [R]: コピー後、プロジェクトのライブラリテーブルへ自動登録する。
3. 「Add New」 を押してリストに登録する。
4. リストの ☑ (Sync Target) にチェックが入っている項目のみが同期対象となる。
5. 「Sync All Checked Operations」ボタンを押すと、チェックされた項目の Clone/Pull、コピー、自動登録が一括実行される。

### 3. ローカルライブラリの登録と取り込み (Local Libraries Import タブ)
1. Source Path に、取り込みたいファイル（.kicad_sym）またはフォルダ（.pretty等を含む解凍済みフォルダ）を指定する（Browse File / Browse Folderボタンを利用可能）。
2. 「Add New」を押してリストに登録する。
3. 取り込みたい項目の ☑ にチェックを入れる。
4. 「Import Checked to Project (Copy & Register)」ボタンを押すと、プロジェクト内の local_imported_libs/ フォルダへ実データがコピーされ、ライブラリテーブルへ即座に自動登録される。

### 4. リストの編集・削除
リストから項目を選択すると、下のテキストボックスにURLやパスが展開される。
内容を書き換えて 「Update Selected...」 を押すと、情報が上書きされる。
不要な場合は 「Remove Selected」 でリストから削除できる（PC上の実ファイルは削除されない）。

>[!NOTE]
>重要: 自動登録機能が実行された後は、KiCadが古いライブラリ情報をメモリに保持している可能性があるため、設定を確実に反映させるために回路図エディタ・PCBエディタを一度開き直してください。

## トラブルシューティング
### プラグインのアイコンが表示されない
配置したディレクトリパスが間違っていないか確認。
git_sync_gui.py が正しく配置されているか確認。

### GitのPull/Cloneが[FAIL]になる
git コマンドのパスが通っていないか、URLが間違っている可能性がある。
ローカルディレクトリに .git が無い空ではないフォルダが存在する場合、安全保護のためCloneは失敗する。エクスプローラから該当フォルダを削除してから再度実行。

### コピーや登録が [SKIP] またはエラーになる
基板ファイル（PCB）が一度も保存されていない（現在のパスが存在しない）場合や、KiCad外からスタンドアロンで実行した場合は、プロジェクトが特定できないためコピーと登録はスキップされる。

### 設定が保存されない・消えた
設定は ~/.kicad_lib_sync.json に保存される。ユーザーのホームディレクトリに書き込み権限がない環境ではエラーになる。