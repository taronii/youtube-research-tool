# YouTube 人気動画リサーチツール

YouTube Data APIを利用した人気動画リサーチツールです。キーワード検索に基づく動画情報を取得し、データを可視化します。さらにGitHub Actionsにより毎朝9時に自動でCSVを出力する機能も備えています。

## 主な機能

- **キーワード検索**: 任意のキーワードでYouTube動画を最大50件検索
- **データ可視化**: 取得したデータをブラウザ上で確認でき、CSVエクスポートも可能
- **チャンネル情報**: チャンネル登録者数も取得し、上振れ係数（再生数÷登録者数）を算出
- **24時間再生数推定**: 前回データとの差分から24時間以内の再生数を推定
- **自動更新**: GitHub Actionsによる毎朝9時の自動CSV出力

## 技術スタック

- **言語**: Python
- **フレームワーク**: Streamlit
- **自動化**: GitHub Actions
- **データ保存**: Googleスプレッドシート
- **APIキー管理**: .envファイル / Streamlit Secrets

## セットアップ方法

### 1. 必要なAPIキーとアカウントの準備

- **YouTube Data API**:
  1. [Google Cloud Platform](https://console.cloud.google.com/)でプロジェクトを作成
  2. YouTube Data API v3を有効化
  3. APIキーを発行

- **Google Sheets API**:
  1. Google Cloud Platformで同プロジェクトにGoogle Sheets APIを有効化
  2. サービスアカウントを作成し、JSONキーをダウンロード
  3. スプレッドシートを作成し、サービスアカウントとの共有設定

### 2. 環境設定

1. リポジトリをクローン
   ```
   git clone <リポジトリURL>
   cd YouTubeリサーチツール
   ```

2. 仮想環境を作成して依存関係をインストール
   ```
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. `.env`ファイルの設定
   ```
   cp .env.sample .env
   ```
   
   `.env`ファイルを編集し、APIキーやGoogleスプレッドシートIDを設定

### 3. 実行方法

**ローカル実行**:
```
streamlit run main.py
```

**自動実行の設定**:
- GitHubリポジトリにプッシュ
- GitHub Secretsに以下の情報を設定:
  - `YOUTUBE_API_KEY`: YouTube APIキー
  - `GOOGLE_SHEETS_ID`: GoogleスプレッドシートのID
  - `GOOGLE_CREDS_JSON`: Googleサービスアカウントの認証情報（JSON全体）
  - `DEFAULT_SEARCH_QUERY`: デフォルト検索キーワード（オプション）

## ファイル構成

- `main.py`: Streamlitアプリ本体
- `get_video_data.py`: YouTube API処理モジュール
- `update_gsheet.py`: スプレッドシート保存処理
- `generate_csv.py`: 毎朝出力用
- `.github/workflows/update.yml`: GitHub Actionsスケジューラ設定
- `.env.sample`: APIキーや認証情報のテンプレート
- `requirements.txt`: 必要パッケージ一覧

## 注意事項

- YouTube APIは1日あたり10,000ポイントのQuota制限があります
- このツールは制限を考慮し、最小限のAPI呼び出しになるよう実装されています
- 推定24時間再生数はGoogleスプレッドシートに保存された過去データを元に計算されます

## ライセンス

MITライセンス
