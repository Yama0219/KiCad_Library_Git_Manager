# KiCad_Library_Git_Manager 

KiCadのシンボルおよびフットプリントライブラリをGitリポジトリ経由で管理し、同期・プロジェクトへのコピー・ライブラリテーブルへの自動登録をワンクリックで行うためのKiCadアクションプラグイン。

## 内容
GUIベースの管理: KiCadのPCBエディタ上から、ダイアログでGitリポジトリ（URLとローカル保存先）の登録・更新・削除が可能。

Git同期: 登録された全リポジトリに対し、ローカルに存在しなければ git clone、存在すれば git pull を自動で判別して一括実行。

プロジェクト・ローカル管理への登録:

[C] Copy: 同期したライブラリを、現在開いているKiCadプロジェクト内の local_git_libs/ フォルダへ自動コピー（容量削減のため .git 履歴データは除外）。

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

Plaintext
plugins/  
    ├─ git_sync_gui.py  
    └─ icon.png  


(※ 設定データは安全のため、プラグインフォルダ内ではなくユーザーのホームディレクトリ ~/.kicad_lib_sync.json に保存される。)

## 使い方 (Usage)
1. プラグインの起動
KiCadから: PCBエディタのツールバーアイコン、または上部メニュー「ツール」>「外部プラグイン」>「Git Library Sync Manager」をクリックする。

スタンドアロン起動: コマンドプロンプトやターミナルから以下を実行する。

Bash
python git_sync_gui.py

1. リポジトリの登録
画面下部の Git URL に、対象のライブラリリポジトリURLを入力する（例: https://github.com/example/kicad-libs.git）。
Local Dir に、PC上でライブラリを保存するディレクトリを指定する（Browseボタンから選択可能）。
対象プロジェクトにデータを引き継ぎたい場合は、以下のオプションにチェックを入れる。
    * Copy to current project folder: 同期後、プロジェクトフォルダへコピーする。
    * Register to project library table: コピー後、プロジェクトのライブラリテーブルへ自動登録する。
「Add New」 を押してリストに登録する。

1. リポジトリの編集・削除  
リストから項目を選択すると、下のテキストボックスにURLとディレクトリが展開される。
URLやディレクトリを書き換えて 「Update Selected URL/Dir」 を押すと、情報が上書きされる。
不要な場合は 「Remove Selected」 でリストから削除できる（PC上の実ファイルは削除されない）。

1. 同期と反映の実行 (Sync Operations)
KiCadのプロジェクトファイル（.kicad_pcb）が開かれており、一度でも「保存」されていることを確認する（未保存の新規プロジェクトではコピー機能が作動しません）。ダイアログ下部の 「Sync All Operations」 ボタンをクリックする。プログレスバーが表示され、以下の処理が自動で進行する。
    * 指定したローカルディレクトリへの Clone / Pull。
    * （チェックが入っている場合）現在のプロジェクトフォルダ内の local_git_libs/ へのファイルコピー。
    * （チェックが入っている場合）シンボル（.kicad_sym）とフットプリント（.pretty）の検索と、プロジェクトライブラリテーブルへの追記。
完了後、Result Summary画面で成否とログを確認できる。

> 重要: 「Register（自動登録）」が実行された後は、KiCadが古いライブラリ情報をメモリに保持している可能性があるため、設定を確実に反映させるために回路図エディタ・PCBエディタを一度開き直してください。

## トラブルシューティング
### プラグインのアイコンが表示されない

配置したディレクトリパスが間違っていないか確認。

git_sync_gui.py が正しく配置されているか確認。

### GitのPull/Cloneが[FAIL]になる

git コマンドのパスが通っていないか、URLが間違っている可能性がある。

ローカルディレクトリに .git が無い空ではないフォルダが存在する場合、安全保護のためCloneは失敗する。エクスプローラから該当フォルダを削除してから再度実行。

### コピーや登録が [SKIP] になる

基板ファイル（PCB）が一度も保存されていない（現在のパスが存在しない）場合や、KiCad外からスタンドアロンで実行した場合は、プロジェクトが特定できないためコピーと登録はスキップされる。

### 設定が保存されない・消えた

設定は ~/.kicad_lib_sync.json に保存される。ユーザーのホームディレクトリに書き込み権限がない環境ではエラーになる。