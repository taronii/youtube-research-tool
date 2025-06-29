import os
import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import datetime
from dotenv import load_dotenv
import base64
import logging
from typing import List, Dict, Any
import html

# Local imports
from get_video_data import YouTubeDataAPI
from update_gsheet import GoogleSheetsManager
from keyword_suggestions import KeywordSuggestionManager
from tag_analyzer import TagAnalyzer
from time_analyzer import TimeAnalyzer
from channel_analyzer import ChannelAnalyzer
from keyword_analyzer import KeywordAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 環境変数の取得（ローカル開発とStreamlit Cloud両方に対応）
def get_api_key():
    """環境に応じてAPIキーを取得。
    優先順位:
    1. .env（ローカル開発）
    2. Streamlit Cloud の secrets.toml
    いずれも無い場合は空文字を返す。
    """
    # まず .env を読み込む（存在しなくても問題ない）
    load_dotenv()
    env_key = os.environ.get("YOUTUBE_API_KEY")
    if env_key:
        return env_key

    # .env に無ければ Streamlit Cloud の secrets を試す
    try:
        return st.secrets.get("YOUTUBE_API_KEY", "")
    except FileNotFoundError:
        # secrets.toml が無いローカル環境では FileNotFoundError が発生する
        return ""


# Function to create a download link for the dataframe
def get_csv_download_link(df, filename="youtube_data.csv"):
    csv = df.to_csv(index=False, encoding='utf-8-sig')
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'''
    <div style="position: fixed; bottom: 30px; right: 30px; z-index: 1000;">
        <a href="data:file/csv;base64,{b64}" download="{filename}" 
           style="background-color: #4CAF50; color: white; padding: 12px 20px; 
                  text-align: center; text-decoration: none; display: inline-block; 
                  font-size: 16px; margin: 4px 2px; cursor: pointer; border-radius: 10px;">
           📥 CSVをダウンロード
        </a>
    </div>
    '''
    return href

# Format video data for display
def format_for_display(df):
    try:
        # dfが存在するかどうか確認
        if df is None or len(df) == 0:
            # 空のデータフレームを返すと後続の処理がエラーになる可能性があるので、
            # 必要なカラムを持つ空のデータフレームを作成して返す
            columns = ['thumbnail', 'title', 'channel_name', 'published_at', 'view_count', 
                      'like_count', 'comment_count', 'subscriber_count', 
                      'engagement_ratio', 'estimated_24h_views', 'thumbnail_url']
            return pd.DataFrame(columns=columns)
        
        # データフレームのコピーを作成
        df_display = df.copy()
        
        # 名前の変更と関数調整
        if 'view_count' in df_display.columns:
            df_display['view_count'] = df_display['view_count'].fillna(0).astype(int)
        if 'like_count' in df_display.columns:
            df_display['like_count'] = df_display['like_count'].fillna(0).astype(int)
        if 'comment_count' in df_display.columns:
            df_display['comment_count'] = df_display['comment_count'].fillna(0).astype(int)
        if 'subscriber_count' in df_display.columns:
            df_display['subscriber_count'] = df_display['subscriber_count'].fillna(0).astype(int)
        if 'estimated_24h_views' in df_display.columns:
            df_display['estimated_24h_views'] = df_display['estimated_24h_views'].fillna(0).astype(int)
        if 'engagement_ratio' in df_display.columns:
            df_display['engagement_ratio'] = df_display['engagement_ratio'].fillna(0).round(2)
        if 'published_at' in df_display.columns and df_display['published_at'].dtype == 'object':
            df_display['published_at'] = pd.to_datetime(df_display['published_at']).dt.strftime('%Y-%m-%d')
        
        return df_display
    except Exception as e:
        st.error(f"Display format error: {e}")
        # エラーハンドリングとして、必要なカラムを持つ空のデータフレームを返す
        columns = ['thumbnail', 'title', 'channel_name', 'published_at', 'view_count', 
                  'like_count', 'comment_count', 'subscriber_count', 
                  'engagement_ratio', 'estimated_24h_views', 'thumbnail_url']
        return pd.DataFrame(columns=columns)

def display_thumbnail(url):
    """Display thumbnail with responsive HTML"""
    return f'<div class="thumbnail-container"><img src="{url}" /></div>'

def main():
    # Streamlitの設定（必ず最初に呼び出す）
    st.set_page_config(
        page_title="YouTube人気動画リサーチツール",
        page_icon="🎥",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # セッション状態の初期化 - 全ての重要な変数を確実に初期化
    if 'channel_comparison_ids_main' not in st.session_state:
        st.session_state.channel_comparison_ids_main = ""
    if 'new_search_query' not in st.session_state:
        st.session_state.new_search_query = ""
    if 'df' not in st.session_state:
        st.session_state.df = None
    if 'processed_df' not in st.session_state:
        st.session_state.processed_df = None
    if 'search_history' not in st.session_state:
        st.session_state.search_history = []
    if 'video_data' not in st.session_state:
        st.session_state.video_data = None
    if 'keywords_data' not in st.session_state:
        st.session_state.keywords_data = {}
    if 'combined_df' not in st.session_state:
        st.session_state.combined_df = None
    
    # 視認性を重視したカスタムCSS
    st.markdown("""
    <style>
        /* 基本設定 - 読みやすさを最優先 */
        .main .block-container {
            padding: 1rem 2rem;
            max-width: 1200px;
            background-color: #f8f9fa;
        }
        
        /* テキストの視認性向上 */
        * {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        
        h1, h2, h3, h4, h5, h6 {
            color: #1f2937 !important;
            font-weight: 600 !important;
            line-height: 1.4 !important;
        }
        
        h1 {
            font-size: 2rem !important;
            margin-bottom: 1.5rem !important;
            padding-bottom: 0.5rem !important;
            border-bottom: 3px solid #3b82f6 !important;
        }
        
        h2 {
            font-size: 1.5rem !important;
            margin-bottom: 1rem !important;
            color: #374151 !important;
        }
        
        h3 {
            font-size: 1.25rem !important;
            margin-bottom: 0.75rem !important;
            color: #4b5563 !important;
        }
        
        /* 本文テキストの視認性 */
        p, div, span, label {
            color: #374151 !important;
            line-height: 1.6 !important;
        }
        
        /* サイドバーの改善 */
        .css-1d391kg {
            background-color: white !important;
            border-right: 1px solid #e5e7eb !important;
        }
        
        /* カードスタイル - 視認性重視 */
        .card {
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            margin: 1rem 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            border: 1px solid #e5e7eb;
        }
        
        /* フォーム要素の改善 */
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea,
        .stSelectbox > div > div > div {
            background-color: white !important;
            border: 2px solid #d1d5db !important;
            border-radius: 8px !important;
            padding: 12px 16px !important;
            font-size: 16px !important;
            color: #374151 !important;
            transition: border-color 0.2s ease !important;
        }
        
        .stTextInput > div > div > input:focus,
        .stTextArea > div > div > textarea:focus {
            border-color: #3b82f6 !important;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
        }
        
        /* ボタンの改善 - タップしやすく */
        .stButton > button {
            background: linear-gradient(135deg, #3b82f6, #1d4ed8) !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 12px 24px !important;
            font-size: 16px !important;
            font-weight: 600 !important;
            width: 100% !important;
            min-height: 48px !important;
            transition: all 0.2s ease !important;
            box-shadow: 0 2px 4px rgba(59, 130, 246, 0.2) !important;
        }
        
        .stButton > button:hover {
            background: linear-gradient(135deg, #1d4ed8, #1e40af) !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 4px 8px rgba(59, 130, 246, 0.3) !important;
        }
        
        .stButton > button:active {
            transform: translateY(0) !important;
        }
        
        /* タブの改善 */
        .stTabs [data-baseweb="tab-list"] {
            background-color: #f3f4f6;
            border-radius: 8px;
            padding: 4px;
            margin-bottom: 1rem;
        }
        
        .stTabs [data-baseweb="tab"] {
            background-color: transparent !important;
            border-radius: 6px !important;
            color: #6b7280 !important;
            font-weight: 500 !important;
            padding: 8px 16px !important;
            transition: all 0.2s ease !important;
        }
        
        .stTabs [aria-selected="true"] {
            background-color: white !important;
            color: #1f2937 !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
        }
        
        /* メトリクスカードの改善 */
        .metric-card {
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            border: 1px solid #e5e7eb;
            transition: transform 0.2s ease;
        }
        
        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.12);
        }
        
        .metric-value {
            font-size: 2rem;
            font-weight: 700;
            color: #1f2937;
            margin-bottom: 0.5rem;
        }
        
        .metric-label {
            font-size: 0.875rem;
            color: #6b7280;
            font-weight: 500;
        }
        
        /* データテーブルの改善 */
        .stDataFrame {
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            border: 1px solid #e5e7eb;
        }
        
        /* エラー・警告メッセージの改善 */
        .stAlert {
            border-radius: 8px !important;
            border: none !important;
            font-weight: 500 !important;
        }
        
        .stError {
            background-color: #fef2f2 !important;
            color: #dc2626 !important;
            border-left: 4px solid #dc2626 !important;
        }
        
        .stWarning {
            background-color: #fffbeb !important;
            color: #d97706 !important;
            border-left: 4px solid #d97706 !important;
        }
        
        .stSuccess {
            background-color: #f0fdf4 !important;
            color: #16a34a !important;
            border-left: 4px solid #16a34a !important;
        }
        
        .stInfo {
            background-color: #eff6ff !important;
            color: #2563eb !important;
            border-left: 4px solid #2563eb !important;
        }
        
        /* スピナーの改善 */
        .stSpinner {
            text-align: center;
            color: #3b82f6 !important;
        }
        
        /* レスポンシブ対応 */
        @media (max-width: 768px) {
            .main .block-container {
                padding: 1rem;
            }
            
            h1 {
                font-size: 1.5rem !important;
            }
            
            .metric-card {
                padding: 1rem;
            }
            
            .metric-value {
                font-size: 1.5rem;
            }
        }
    </style>
    """, unsafe_allow_html=True)
    
    # 追加のカスタムスタイル
    st.markdown("""
    <style>
    /* CSVダウンロードボタンの改善 */
    .download-button {
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 1000;
        background: linear-gradient(135deg, #10b981, #059669);
        color: white;
        padding: 12px 16px;
        border-radius: 50px;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
        text-decoration: none;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    .download-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(16, 185, 129, 0.4);
    }
    /* サムネイル画像の改善 */
    .thumbnail-container {
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: transform 0.2s ease;
    }
    .thumbnail-container:hover {
        transform: scale(1.05);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    .thumbnail-container img {
        width: 100%;
        height: auto;
        display: block;
    }
    /* プログレスバーの改善 */
    .stProgress > div > div {
        background: linear-gradient(90deg, #3b82f6, #1d4ed8);
        border-radius: 4px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <style>
    /* CSVダウンロードボタンの改善 */
    .download-button {
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 1000;
        background: linear-gradient(135deg, #10b981, #059669);
        color: white;
        padding: 12px 16px;
        border-radius: 50px;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
        text-decoration: none;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    
    .download-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(16, 185, 129, 0.4);
    }
    
    /* サムネイル画像の改善 */
    .thumbnail-container {
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: transform 0.2s ease;
    }
    
    .thumbnail-container:hover {
        transform: scale(1.05);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    
    .thumbnail-container img {
        width: 100%;
        height: auto;
        display: block;
    }
    
    /* プログレスバーの改善 */
    .stProgress > div > div {
        background: linear-gradient(90deg, #3b82f6, #1d4ed8);
        border-radius: 4px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # メインタイトル
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem;">
        <h1 style="color: #1f2937; font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem;">
🎥 YouTube人気動画リサーチツール
        </h1>
        <p style="color: #6b7280; font-size: 1.1rem; margin: 0;">
            人気動画を分析して、トレンドを把握しましょう
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar for search options
    st.sidebar.header("検索設定")
    
    # Get API key - get_api_key関数を使用してローカル/.envとStreamlit Cloudの両方に対応
    api_key = get_api_key()
    logger.info(f"Main function - API Key available: {bool(api_key)}")
    
    # API Key input - APIキーが取得できなかった場合はユーザー入力を求める
    if not api_key:
        st.sidebar.markdown("""
        <div style="background-color: #f8d7da; padding: 10px; border-radius: 10px; margin-bottom: 10px;">
            <h4 style="color: #721c24; margin: 0;">⚠️ API Key Required</h4>
            <p style="margin: 5px 0 0 0;">YouTube Data APIのキーが必要です</p>
        </div>
        """, unsafe_allow_html=True)
        
        api_key = st.sidebar.text_input("YouTube API Key", 
                                        type="password",
                                        help="YouTube Data APIのキーを入力してください")
    
    # Default search params
    default_query = os.getenv('DEFAULT_SEARCH_QUERY', 'プログラミング')
    max_results = int(os.getenv('MAX_RESULTS', '50'))
    
    # Search form
    with st.sidebar.form("search_form"):
        search_query = st.text_area("検索キーワード（複数の場合はカンマ区切りまたは改行）", 
                               value=default_query, 
                               placeholder="例：筋トレ\nモチベーション\nダイエット\n\n※複数キーワードを入力すると比較できます",
                               height=100)
        result_limit = st.slider("取得件数", min_value=10, max_value=50, value=max_results, step=10)
        
        # 投稿期間指定機能（エキスパンダーに入れる）
        date_filter_expander = st.expander("投稿期間指定", expanded=False)
        with date_filter_expander:
            date_filter = st.selectbox(
                "期間",
                [
                    "指定なし",
                    "直近24時間",
                    "直近7日間",
                    "直近30日間",
                    "カスタム期間"
                ],
                index=0
            )
            
            # カスタム期間の場合は日付選択UIを表示
            custom_dates = None
            if date_filter == "カスタム期間":
                start_date = st.date_input("開始日", datetime.now() - pd.Timedelta(days=7))
                end_date = st.date_input("終了日", datetime.now())
                custom_dates = (start_date, end_date)
        
        # 検索ボタンをタップしやすく大きくする
        submitted = st.form_submit_button("検索", use_container_width=True)
    
    # Initialize session state for keyword search
    if 'new_search_query' in st.session_state and st.session_state.new_search_query:
        search_query = st.session_state.new_search_query
        st.session_state.new_search_query = ""  # 値を削除する代わりに空文字列に設定
    
    # Main content
    if submitted or st.session_state.video_data is not None:
        if not api_key:
            st.error("YouTube API Keyが必要です。サイドバーで入力してください。")
            return
        
        # Show loading message during API calls
        if submitted:
            with st.spinner('YouTubeからデータを取得中...'):
                try:
                    # Initialize YouTube API client
                    youtube_client = YouTubeDataAPI(api_key)
                    
                    # Try to initialize Google Sheets manager
                    try:
                        sheets_manager = GoogleSheetsManager()
                        previous_stats = sheets_manager.get_previous_stats()
                    except Exception as e:
                        st.warning(f"Googleスプレッドシートへの接続に失敗しました。履歴データなしで続行します: {e}")
                        previous_stats = {}
                        sheets_manager = None
                    
                    # Search for videos with date filters if specified
                    published_after = None
                    published_before = None
                    
                    # Convert date filter selection to actual date parameters
                    if date_filter == "直近24時間":
                        published_after = (datetime.now() - pd.Timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
                    elif date_filter == "直近7日間":
                        published_after = (datetime.now() - pd.Timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
                    elif date_filter == "直近30日間":
                        published_after = (datetime.now() - pd.Timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
                    elif date_filter == "カスタム期間" and custom_dates:
                        # Convert datetime.date to full datetime with time
                        start_datetime = datetime.combine(custom_dates[0], datetime.min.time())
                        end_datetime = datetime.combine(custom_dates[1], datetime.max.time())
                        published_after = start_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")
                        published_before = end_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")
                    
                    # Log the date filters
                    if published_after or published_before:
                        st.sidebar.info(f"\u6295稿期間フィルター: {date_filter}")
                        logger.info(f"Applying date filters: after={published_after}, before={published_before}")
                    
                    # 複数キーワード処理: カンマまたは改行で分割
                    # カンマでまず分割し、その後各要素内の改行で分割
                    keywords = []
                    if search_query:
                        # カンマ区切りを処理
                        comma_separated = search_query.split(',')
                        for item in comma_separated:
                            # 改行区切りを処理
                            newline_separated = [k.strip() for k in item.split('\n') if k.strip()]
                            keywords.extend(newline_separated)
                    
                    if not keywords:
                        keywords = [search_query]  # 区切りがない場合は単一キーワードとして処理
                    
                    # 各キーワードについて検索を実行
                    st.session_state.keywords_data = {}  # リセット
                    
                    for idx, keyword in enumerate(keywords):
                        if not keyword.strip():
                            continue
                            
                        with st.spinner(f'「{keyword}」の検索結果を取得中... ({idx+1}/{len(keywords)})'):
                            # Call API with date filters for this keyword
                            video_ids = youtube_client.search_videos(
                                keyword, 
                                result_limit,
                                published_after=published_after,
                                published_before=published_before
                            )
                            
                            if not video_ids:
                                st.warning(f"キーワード「{keyword}」では検索条件に一致する動画が見つかりませんでした。")
                                continue
                            
                            # Get video details
                            videos_data = youtube_client.get_videos_details(video_ids)
                            
                            # Extract channel IDs
                            channel_ids = [video.get('snippet', {}).get('channelId') 
                                        for video in videos_data if video.get('snippet')]
                            
                            # Get channel details
                            channels_data = youtube_client.get_channel_details(channel_ids)
                            
                            # Format video data
                            formatted_data = youtube_client.format_video_data(
                                videos_data, 
                                channels_data,
                                previous_stats
                            )
                            
                            # Store in session state for this keyword
                            if formatted_data:
                                df_keyword = pd.DataFrame(formatted_data)
                                df_keyword['search_keyword'] = keyword  # キーワード情報を追加
                                st.session_state.keywords_data[keyword] = {
                                    'data': formatted_data,
                                    'df': df_keyword
                                }
                    
                    # キーワードデータが何もない場合はエラーを表示
                    if not st.session_state.keywords_data:
                        st.error("どのキーワードでも検索結果が得られませんでした。検索条件を変更してお試しください。")
                        return
                        
                    # 最初のキーワードのデータをメインデータとして設定（互換性のため）
                    first_keyword = next(iter(st.session_state.keywords_data))
                    st.session_state.video_data = st.session_state.keywords_data[first_keyword]['data']
                    st.session_state.df = st.session_state.keywords_data[first_keyword]['df']
                    
                    # 全てのキーワードのデータを結合したデータフレームも作成
                    all_dfs = [data['df'] for data in st.session_state.keywords_data.values()]
                    if all_dfs:
                        st.session_state.combined_df = pd.concat(all_dfs, ignore_index=True)
                    else:
                        st.session_state.combined_df = None
                    
                    # Try to update Google Sheets if connected (最初のキーワードのみ)
                    if sheets_manager is not None:
                        try:
                            sheets_manager.update_video_history(st.session_state.video_data)
                            sheets_manager.update_current_data(st.session_state.video_data)
                        except Exception as e:
                            st.warning(f"Googleスプレッドシートの更新に失敗しました: {e}")
                    
                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")
                    return
        
        # Display data
        if st.session_state.video_data and hasattr(st.session_state, 'keywords_data'):
            # タブを表示（複数キーワード対応）
            if len(st.session_state.keywords_data) > 1:
                # 複数キーワードがある場合はタブで表示
                tab_labels = list(st.session_state.keywords_data.keys())
                tab_labels.append("キーワード比較")
                
                tabs = st.tabs(tab_labels)
                
                # 各キーワードごとのタブ内容
                for i, (keyword, keyword_data) in enumerate(st.session_state.keywords_data.items()):
                    with tabs[i]:
                        st.header(f"キーワード：{keyword}の検索結果")
                        df = keyword_data['df']
                        
                # キーワード比較タブ
                with tabs[-1]:
                    st.header("キーワードごとの成功傾向分析")
                    
                    # 各キーワードの成功指標を計算
                    trend_data = []
                    for keyword, data in st.session_state.keywords_data.items():
                        df_keyword = data['df']
                        
                        # 平均再生数
                        avg_views = df_keyword['view_count'].mean()
                        
                        # 平均上振れ率
                        avg_engagement = df_keyword['engagement_ratio'].mean()
                        
                        # 平均動画長（秒）
                        # duration_secondsカラムが存在する場合はその平均を計算、ない場合は0を設定
                        if 'duration_seconds' in df_keyword.columns:
                            avg_duration = df_keyword['duration_seconds'].mean()
                        else:
                            # 動画長データが存在しない場合は仮の値
                            st.warning(f"キーワード「{keyword}」の動画長データが利用できませんでした。")
                            avg_duration = 0
                        
                        # 平均コメント率
                        avg_comment_ratio = (df_keyword['comment_count'] / df_keyword['view_count']).mean()
                        
                        # 動画数
                        video_count = len(df_keyword)
                        
                        trend_data.append({
                            'キーワード': keyword,
                            '動画数': video_count,
                            '平均再生数': avg_views,
                            '平均上振れ率': avg_engagement,
                            '平均動画長(秒)': avg_duration,
                            '平均コメント率': avg_comment_ratio
                        })
                    
                    # データフレーム化して表示
                    if trend_data:
                        df_trends = pd.DataFrame(trend_data)
                        
                        # 数値フォーマットを整える
                        df_trends['平均再生数'] = df_trends['平均再生数'].map('{:,.0f}'.format)
                        df_trends['平均上振れ率'] = df_trends['平均上振れ率'].map('{:.2f}'.format)
                        df_trends['平均動画長(秒)'] = df_trends['平均動画長(秒)'].map('{:.0f}'.format)
                        df_trends['平均コメント率'] = df_trends['平均コメント率'].map('{:.4f}'.format)
                        
                        # テーブル表示
                        st.subheader("キーワード比較表")
                        st.markdown('<div class="dataframe-container">', unsafe_allow_html=True)
                        if len(df_trends) > 0:
                            st.dataframe(df_trends, use_container_width=True)
                        else:
                            st.warning("表示するデータがありません。")
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        # 収集した数値データを使用して棒グラフを作成
                        # データをグラフ用に整形
                        df_chart = pd.DataFrame(trend_data)
                        
                        # 再生数グラフ
                        st.subheader("平均再生数比較")
                        fig_views = px.bar(
                            df_chart, 
                            x='キーワード', 
                            y='平均再生数',
                            color='キーワード',
                            text_auto='.2s'
                        )
                        fig_views.update_layout(
                            height=400,
                            plot_bgcolor='rgba(255,255,255,0.95)',
                            paper_bgcolor='rgba(255,255,255,0)',
                        )
                        st.plotly_chart(fig_views, use_container_width=True)
                        
                        # 上振れ率グラフ
                        st.subheader("平均上振れ率比較")
                        fig_engagement = px.bar(
                            df_chart, 
                            x='キーワード', 
                            y='平均上振れ率',
                            color='キーワード',
                            text_auto='.2f'
                        )
                        fig_engagement.update_layout(
                            height=400,
                            plot_bgcolor='rgba(255,255,255,0.95)',
                            paper_bgcolor='rgba(255,255,255,0)',
                        )
                        st.plotly_chart(fig_engagement, use_container_width=True)
                        
                        # 動画長とコメント率の比較グラフ - スマホ対応のために縦並びに変更
                        # 動画長グラフ
                        st.subheader("平均動画長比較")
                        fig_duration = px.bar(
                            df_chart, 
                            x='キーワード', 
                            y='平均動画長(秒)',
                            color='キーワード',
                            text_auto='.0f'
                        )
                        fig_duration.update_layout(
                            height=400,
                            plot_bgcolor='rgba(255,255,255,0.95)',
                            paper_bgcolor='rgba(255,255,255,0)',
                        )
                        st.plotly_chart(fig_duration, use_container_width=True)
                        
                        # コメント率グラフ
                        st.subheader("平均コメント率比較")
                        fig_comments = px.bar(
                            df_chart, 
                            x='キーワード', 
                            y='平均コメント率',
                            color='キーワード',
                            text_auto='.4f'
                        )
                        fig_comments.update_layout(
                            height=400,
                            plot_bgcolor='rgba(255,255,255,0.95)',
                            paper_bgcolor='rgba(255,255,255,0)',
                        )
                        st.plotly_chart(fig_comments, use_container_width=True)
                            
                        st.info("※ 上振れ率が高いキーワードは、チャネル登録者数に対して多くの再生数を獲得している市場です。コメント率が高いキーワードは視聴者の反応が活発です。")

            # --- フィルタリング・ソート統合セクション ---
            st.markdown("""
            <div style="background: white; border-radius: 20px; padding: 24px; margin: 20px 0; 
                        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.08); border: 1px solid rgba(102, 126, 234, 0.1);">
                <h4 style="color: #667eea; margin: 0 0 20px 0; font-weight: 600; text-align: center;">
                    🎛️ データフィルター & ソート
                </h4>
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            
            # 現在のデータフレームを取得（検索結果から開始）
            current_df = df.copy() if 'df' in locals() and df is not None else None
            
            with col1:
                st.markdown("**📹 動画タイプ**")
                # 動画タイプフィルター
                video_filter = st.selectbox(
                    "",
                    ["すべて", "ショート動画のみ", "長編動画のみ"],
                    key="video_type_filter",
                    help="表示する動画の種類を選択してください"
                )
            
            with col2:
                st.markdown("**📊 並び替え**")
                # ソート順序選択機能の追加
                sort_option = st.selectbox(
                    "",
                    [
                        "再生数順 (多い順)",
                        "上振れ率順 (高い順)",
                        "コメント数順 (多い順)",
                        "コメント率順 (高い順)",
                        "投稿日順 (新しい順)",
                        "投稿日順 (古い順)"
                    ],
                    index=0,
                    key="sort_option",
                    help="データの並び順を選択してください"
                )
            
            # フィルタリング・ソート処理を統合実行
            if current_df is not None and len(current_df) > 0:
                try:
                    # Step 1: フィルタリング処理
                    if 'video_type' in current_df.columns:
                        pre_filter_count = len(current_df)
                        
                        if video_filter == "ショート動画のみ":
                            current_df = current_df[current_df['video_type'] == 'short']
                            if len(current_df) > 0:
                                if len(current_df) < pre_filter_count:
                                    st.info(f"ショート動画のみ表示しています（{len(current_df)}件）")
                            else:
                                st.warning("条件に一致するショート動画が見つかりませんでした。元のデータを表示します。")
                                current_df = df.copy()  # 元のデータに戻す
                        elif video_filter == "長編動画のみ":
                            current_df = current_df[current_df['video_type'] == 'long']
                            if len(current_df) > 0:
                                if len(current_df) < pre_filter_count:
                                    st.info(f"長編動画のみ表示しています（{len(current_df)}件）")
                            else:
                                st.warning("条件に一致する長編動画が見つかりませんでした。元のデータを表示します。")
                                current_df = df.copy()  # 元のデータに戻す
                    else:
                        if video_filter != "すべて":
                            st.warning("動画タイプ情報が利用できません。フィルタリングをスキップします。")
                    
                    # Step 2: ソート処理（フィルタリング後のデータに対して実行）
                    if len(current_df) > 0:
                        if sort_option == "再生数順 (多い順)":
                            current_df = current_df.sort_values(by='view_count', ascending=False)
                        elif sort_option == "上振れ率順 (高い順)":
                            current_df = current_df.sort_values(by='engagement_ratio', ascending=False)
                            # 上振れ率ランキングが選択された場合、上位5件に印を付ける
                            top_engaging_videos = current_df.nlargest(min(5, len(current_df)), 'engagement_ratio').index.tolist()
                            st.session_state.top_engaging_videos = top_engaging_videos
                        elif sort_option == "コメント数順 (多い順)":
                            current_df = current_df.sort_values(by='comment_count', ascending=False)
                            # コメント数の多い上位5件に印を付ける
                            top_commented_videos = current_df.nlargest(min(5, len(current_df)), 'comment_count').index.tolist()
                            st.session_state.top_commented_videos = top_commented_videos
                            # タイトルにコメント数が多いことを示すマークを追加
                            current_df = current_df.copy()
                            current_df['title'] = current_df.apply(
                                lambda row: f"🔥 {row['title']}" if row.name in top_commented_videos else row['title'],
                                axis=1
                            )
                        elif sort_option == "コメント率順 (高い順)":
                            # コメント率を計算
                            current_df = current_df.copy()
                            current_df['comment_ratio'] = current_df['comment_count'] / current_df['view_count']
                            current_df = current_df.sort_values(by='comment_ratio', ascending=False)
                        elif sort_option == "投稿日順 (新しい順)":
                            current_df = current_df.sort_values(by='published_at', ascending=False)
                        elif sort_option == "投稿日順 (古い順)":
                            current_df = current_df.sort_values(by='published_at', ascending=True)
                    
                    # 最終的な処理済みデータフレームをセッションステートに保存
                    st.session_state.processed_df = current_df
                    df = current_df  # ローカル変数も更新
                    
                except Exception as e:
                    st.error(f"データの処理中にエラーが発生しました: {e}")
                    # エラーが発生した場合は元のデータを使用
                    st.session_state.processed_df = df
            else:
                st.warning("表示するデータがありません。検索条件を変更してください。")
            
            # Summary metrics
            st.markdown("""
            <div style="background: white; border-radius: 20px; padding: 24px; margin: 30px 0; 
                        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.08); border: 1px solid rgba(102, 126, 234, 0.1);">
                <h4 style="color: #667eea; margin: 0 0 20px 0; font-weight: 600; text-align: center;">
                    📊 データサマリー
                </h4>
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2, col3, col4 = st.columns(4)
            
            # 処理済みデータフレームの取得
            # 統合処理後のデータフレームがあればそれを使用
            if 'processed_df' in st.session_state and st.session_state.processed_df is not None:
                df = st.session_state.processed_df
            # なければセッションステートから最新のdfを取得
            elif 'df' in st.session_state and st.session_state.df is not None:
                df = st.session_state.df
            
            # df変数が存在し、データがあるか確認
            if 'df' in locals() and df is not None and len(df) > 0:
                with col1:
                    st.markdown("""
                    <div class="metric-card" style="background: linear-gradient(135deg, #667eea, #764ba2);">
                        <div class="metric-value">{}</div>
                        <div class="metric-label">📹 取得動画数</div>
                    </div>
                    """.format(len(df) if df is not None else 0), unsafe_allow_html=True)
                
                with col2:
                    if df is not None and len(df) > 0 and 'view_count' in df.columns:
                        total_views = df['view_count'].sum()
                        if total_views >= 1_000_000:
                            total_views_str = f"{total_views/1_000_000:.1f}M"
                        elif total_views >= 1_000:
                            total_views_str = f"{total_views/1_000:.1f}K"
                        else:
                            total_views_str = str(total_views)
                        st.markdown("""
                        <div class="metric-card" style="background: linear-gradient(135deg, #48bb78, #38a169);">
                            <div class="metric-value">{}</div>
                            <div class="metric-label">👀 総再生回数</div>
                        </div>
                        """.format(total_views_str), unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div class="metric-card" style="background: linear-gradient(135deg, #48bb78, #38a169);">
                            <div class="metric-value">N/A</div>
                            <div class="metric-label">👀 総再生回数</div>
                        </div>
                        """, unsafe_allow_html=True)
                
                with col3:
                    if df is not None and len(df) > 0 and 'engagement_ratio' in df.columns:
                        avg_engagement = df['engagement_ratio'].mean()
                        st.markdown("""
                        <div class="metric-card" style="background: linear-gradient(135deg, #fc7d7b, #f093fb);">
                            <div class="metric-value">{:.2f}</div>
                            <div class="metric-label">📈 平均上振れ係数</div>
                        </div>
                        """.format(avg_engagement), unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div class="metric-card" style="background: linear-gradient(135deg, #fc7d7b, #f093fb);">
                            <div class="metric-value">N/A</div>
                            <div class="metric-label">📈 平均上振れ係数</div>
                        </div>
                        """, unsafe_allow_html=True)
                
                with col4:
                    if df is not None and len(df) > 0 and 'estimated_24h_views' in df.columns:
                        total_24h = df['estimated_24h_views'].sum()
                        if total_24h > 0:
                            if total_24h >= 1_000_000:
                                total_24h_str = f"{total_24h/1_000_000:.1f}M"
                            elif total_24h >= 1_000:
                                total_24h_str = f"{total_24h/1_000:.1f}K"
                            else:
                                total_24h_str = str(total_24h)
                            st.markdown("""
                            <div class="metric-card" style="background: linear-gradient(135deg, #f093fb, #f5576c);">
                                <div class="metric-value">{}</div>
                                <div class="metric-label">⚡ 推定24時間再生数</div>
                            </div>
                            """.format(total_24h_str), unsafe_allow_html=True)
                        else:
                            st.markdown("""
                            <div class="metric-card" style="background: linear-gradient(135deg, #f093fb, #f5576c);">
                                <div class="metric-value">N/A</div>
                                <div class="metric-label">⚡ 推定24時間再生数</div>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div class="metric-card" style="background: linear-gradient(135deg, #f093fb, #f5576c);">
                            <div class="metric-value">N/A</div>
                            <div class="metric-label">⚡ 推定24時間再生数</div>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                # データがない場合はダミー表示
                for i, (icon, label) in enumerate([("📹", "取得動画数"), ("👀", "総再生回数"), ("📈", "平均上振れ係数"), ("⚡", "推定24時間再生数")]):
                    with [col1, col2, col3, col4][i]:
                        st.markdown(f"""
                        <div class="metric-card" style="background: linear-gradient(135deg, #cbd5e0, #a0aec0);">
                            <div class="metric-value">0</div>
                            <div class="metric-label">{icon} {label}</div>
                        </div>
                        """, unsafe_allow_html=True)
            
            # 関連キーワードサジェストをサイドバーに表示
            if search_query and len(search_query.strip()) > 1:
                try:
                    suggestion_manager = KeywordSuggestionManager()
                    suggestions = suggestion_manager.get_suggestions(search_query)
                    
                    if suggestions:
                        with st.sidebar.expander("関連キーワード", expanded=True):
                            st.sidebar.markdown(f"**「{search_query}」に関連するキーワード**")
                            for suggestion in suggestions:
                                if st.sidebar.button(f"🔍 {suggestion}", key=f"suggest_{suggestion}", use_container_width=True):
                                    # ボタンクリック時に検索クエリを変更して再検索
                                    st.session_state.new_search_query = suggestion
                                    st.experimental_rerun()
                except Exception as e:
                    logger.error(f"関連キーワード取得エラー: {e}")
            
            # Tabs for different views
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["データテーブル", "チャート", "詳細ビュー", "チャンネル比較", "キーワード比較"])
            
            with tab1:
                # Data table
                st.subheader("検索結果")
                
                # Display the main data table with enhanced formatting
                display_columns = [
                    'thumbnail', 'title', 'channel_name', 'published_at', 'view_count', 
                    'like_count', 'comment_count', 'subscriber_count', 
                    'engagement_ratio', 'estimated_24h_views'
                ]

                # 検索条件で絞り込まれたデータを表示するための処理
                # 統合処理後のデータフレームがあればそれを使用
                if 'processed_df' in st.session_state and st.session_state.processed_df is not None:
                    df = st.session_state.processed_df
                # なければセッションステートから最新のdfを取得
                elif 'df' in st.session_state:
                    df = st.session_state.df
                
                # df変数が存在し、データがあるか確認
                if 'df' not in locals() or df is None or len(df) == 0:
                    st.warning("表示するデータがありません。検索条件を変更してください。")
                else:
                    # Format the data with styles and icons
                    df_display = format_for_display(df.copy())  # 必ずコピーを渡す
                    
                    # df_displayの存在確認
                    if df_display is not None and len(df_display) > 0:
                        # サムネイル画像の表示
                        if 'thumbnail_url' in df_display.columns:
                            # サムネイル画像のHTMLを生成
                            df_display['thumbnail'] = df_display['thumbnail_url'].apply(lambda url: display_thumbnail(url))
                        else:
                            # サムネイル画像のURLがない場合は空の列を追加
                            df_display['thumbnail'] = ''

                # デバッグ情報表示（debug_mode が True のときのみ）
                if st.session_state.get('debug_mode', False):
                    st.write(f"Session 内のデータフレームステータス: {'df' in st.session_state}")
                    if 'df' in st.session_state:
                        st.write(f"Session dfのレコード数: {len(st.session_state.df) if st.session_state.df is not None else 0}")
                    st.write(f"ローカル df ステータス: {'df' in locals()}")
                    if 'df' in locals() and df is not None:
                        st.write(f"ローカル df レコード数: {len(df)}")
                    st.write(f"df_display ステータス: {'df_display' in locals()}")
                    if 'df_display' in locals() and df_display is not None:
                        st.write(f"df_display レコード数: {len(df_display)}")

                # df変数が存在し、データがある場合のみスタイル適用
                if ('df_display' in locals() and df_display is not None and len(df_display) > 0 and
                    all(col in df_display.columns for col in display_columns)):
                    try:
                        # Apply styling with icons and highlighting
                        df_styled = df_display[display_columns].style\
                            .format({
                                'view_count': '👁️ {:,}',
                                'like_count': '👍 {:,}',
                                'comment_count': '💬 {:,}',
                                'subscriber_count': '{:,}',
                                'engagement_ratio': '🔥 {:.2f}',
                                'estimated_24h_views': '⏱️ {:,}'
                            })\
                            .background_gradient(cmap='Greens', subset=['view_count'])\
                            .background_gradient(cmap='Oranges', subset=['engagement_ratio'])\
                            .background_gradient(cmap='Blues', subset=['estimated_24h_views'])
                        
                        # サムネイル画像のHTMLをレンダリングするための設定
                        df_styled = df_styled.format({'thumbnail': lambda x: x}, escape="html")
                        
                        # データ表示成功フラグ
                        styling_success = True
                    except Exception as e:
                        st.error(f"データ表示スタイリングエラー: {e}")
                        styling_success = False
                else:
                    styling_success = False

                # HTMLテーブルのCSS (改善したテーブルスタイリング)
                html_table_css = """
                <style>
                /* 全体のスタイル */
                .main .block-container {
                    padding-top: 1rem;
                    max-width: 1200px;
                }
                
                @media (max-width: 768px) {
                    .main .block-container {
                        padding: 1rem 0.5rem;
                    }
                    
                    /* スマホ用フォントサイズ調整 */
                    table {
                        font-size: 0.8rem;
                    }
                    
                    /* スマホ用見出し調整 */
                    h1 {
                        font-size: 1.5rem;
                    }
                    
                    h2, h3 {
                        font-size: 1.2rem;
                    }
                }
                
                h1, h2, h3 {
                    font-family: 'Helvetica Neue', Arial, sans-serif;
                    color: #2E3B4E;
                    margin-bottom: 1rem;
                }
                
                h1 {
                    font-weight: 700;
                    border-bottom: 2px solid #FF5252;
                    padding-bottom: 0.5rem;
                }
                
                .stTabs [data-baseweb="tab-list"] {
                    gap: 2px;
                }
                
                .stTabs [data-baseweb="tab"] {
                    height: 50px;
                    white-space: pre-wrap;
                    background-color: #f0f2f6;
                    border-radius: 4px 4px 0 0;
                    gap: 1px;
                    padding-top: 10px;
                    padding-bottom: 10px;
                }
                
                .stTabs [aria-selected="true"] {
                    background-color: #4CAF50 !important;
                    color: white !important;
                }
                
                /* カードスタイル */
                div[data-testid="stExpander"] {
                    border: 1px solid #e0e0e0;
                    border-radius: 10px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    margin-bottom: 1rem;
                }
                
                /* チャートスタイル */
                .js-plotly-plot {
                    border-radius: 8px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.08);
                    margin-bottom: 2rem !important;
                    padding: 1rem !important;
                    background: white;
                }
                
                /* ボタンスタイル */
                .stButton > button {
                    border-radius: 20px;
                    font-weight: 500;
                    padding: 0.3rem 1rem;
                    border: none;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                    transition: all 0.3s;
                }
                
                .stButton > button:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 8px rgba(0,0,0,0.15);
                }
                
                /* テーブルコンテナ */
                .youtube-container {
                    overflow-x: auto;
                    border-radius: 10px;
                    margin-bottom: 1rem;
                    border: 1px solid #e0e0e0;
                }
                
                /* テーブルスタイル */
                .youtube-data {
                    width: 100%;
                    border-collapse: separate;
                    border-spacing: 0;
                    font-family: 'Helvetica Neue', Arial, sans-serif;
                    font-size: 0.9em;
                }
                
                .youtube-data thead tr {
                    background: linear-gradient(135deg, #2E3B4E 0%, #4C566A 100%);
                }
                table.youtube-data {
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 0.9em;
                    font-family: sans-serif;
                    box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
                    table-layout: fixed;
                }
                table.youtube-data thead tr {
                    background-color: #1e3d59;
                    color: #ffffff;
                    text-align: left;
                    position: sticky;
                    top: 0;
                }
                table.youtube-data th,
                table.youtube-data td {
                    padding: 10px;
                    border-bottom: 1px solid #dddddd;
                    word-wrap: break-word;
                    overflow-wrap: break-word;
                    vertical-align: top;
                }
                table.youtube-data th.thumbnail {
                    width: 90px;
                    min-width: 90px;
                }
                table.youtube-data th.title {
                    width: 25%;
                }
                table.youtube-data th.channel_name {
                    width: 15%;
                }
                table.youtube-data th.published_at {
                    width: 90px;
                }
                table.youtube-data th.view_count,
                table.youtube-data th.like_count,
                table.youtube-data th.comment_count,
                table.youtube-data th.subscriber_count,
                table.youtube-data th.engagement_ratio,
                table.youtube-data th.estimated_24h_views {
                    width: 8%;
                }
                table.youtube-data tbody tr {
                    border-bottom: 1px solid #dddddd;
                }
                table.youtube-data tbody tr:nth-of-type(even) {
                    background-color: #f9f9f9;
                }
                table.youtube-data tbody tr:hover {
                    background-color: #f1f1f1;
                }
                table.youtube-data .thumbnail-cell img {
                    display: block;
                    border-radius: 5px;
                    width: 80px;
                    height: auto;
                }
                </style>
                """
                
                # データフレームをHTML形式に変換（サムネイル画像とアイコンを表示するために escape=False）
                # レスポンシブな横スクロールを許可するコンテナで囲む
                html_table = "<div class='youtube-container'>\n"
                html_table += "<table class='youtube-data'>\n"
                
                # テーブルヘッダー（各カラムにCSSクラスを適用）
                html_table += "<thead>\n<tr>\n"
                column_headers = {
                    'thumbnail': 'サムネイル',
                    'title': 'タイトル',
                    'channel_name': 'チャンネル名',
                    'published_at': '投稿日',
                    'view_count': '再生数',
                    'like_count': 'いいね数',
                    'comment_count': 'コメント数',
                    'subscriber_count': '登録者数',
                    'engagement_ratio': '上振れ係数',
                    'estimated_24h_views': '24時間推定再生数'
                }
                
                for col in display_columns:
                    header = column_headers.get(col, col)
                    # 各列にクラス名を付与してCSSで幅制御
                    html_table += f"<th class='{col}'>{header}</th>\n"
                html_table += "</tr>\n</thead>\n"
                
                # テーブルボディ
                html_table += "<tbody>\n"
                
                # df_displayが存在し、データがあるか確認
                if 'df_display' in locals() and df_display is not None and len(df_display) > 0:
                    # 行ごとにデータを追加
                    for _, row in df_display[display_columns].iterrows():
                        html_table += "<tr>\n"
                        
                        for col in display_columns:
                            value = row[col]
                            
                            # 列ごとに異なるフォーマットと適切なクラスを追加
                            # セル値を予めフォーマットする
                            if col == 'thumbnail':
                                # サムネイルは専用クラスでスタイリング
                                cell_content = value  # ここではすでにHTMLの<img>タグが生成されている
                                html_table += f"<td class='thumbnail-cell'>{cell_content}</td>\n"
                            elif col == 'title':
                                # タイトルは少し長くても大丈夫なように
                                cell_content = html.escape(str(value))  # 安全のためHTMLエスケープ
                                html_table += f"<td class='title-cell'>{cell_content}</td>\n"
                            elif col == 'channel_name':
                                cell_content = html.escape(str(value))  # 安全のためHTMLエスケープ
                                html_table += f"<td class='channel-cell'>{cell_content}</td>\n"
                            elif col == 'published_at':
                                cell_content = html.escape(str(value))  # 安全のためHTMLエスケープ
                                html_table += f"<td class='date-cell'>{cell_content}</td>\n"
                            elif col == 'view_count':
                                cell_content = f"👁️ {int(value):,}"
                                html_table += f"<td class='numeric-cell'>{cell_content}</td>\n"
                            elif col == 'like_count':
                                cell_content = f"👍 {int(value):,}"
                                html_table += f"<td class='numeric-cell'>{cell_content}</td>\n"
                            elif col == 'comment_count':
                                cell_content = f"💬 {int(value):,}"
                                html_table += f"<td class='numeric-cell'>{cell_content}</td>\n"
                            elif col == 'subscriber_count':
                                cell_content = f"{int(value):,}"
                                html_table += f"<td class='numeric-cell'>{cell_content}</td>\n"
                            elif col == 'engagement_ratio':
                                cell_content = f"🔥 {float(value):.2f}"
                                html_table += f"<td class='numeric-cell highlight-cell'>{cell_content}</td>\n"
                            elif col == 'estimated_24h_views':
                                cell_content = f"⏱️ {int(value):,}"
                                html_table += f"<td class='numeric-cell'>{cell_content}</td>\n"
                            else:
                                # その他の列は標準のフォーマット
                                cell_content = html.escape(str(value))  # 安全のためHTMLエスケープ
                                html_table += f"<td>{cell_content}</td>\n"
                        
                    html_table += "</tr>\n"
                    
                html_table += "</tbody>\n</table>\n</div>"
                
                # CSSとHTMLテーブルを表示
                st.markdown(html_table_css + html_table, unsafe_allow_html=True)
                
                # CSVダウンロードボタンを画面下部に固定表示
                # dfが存在しデータがある場合のみダウンロードボタンを表示
                if 'df' in locals() and df is not None and len(df) > 0:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"youtube_data_{timestamp}.csv"
                    st.markdown(get_csv_download_link(df, filename=filename), unsafe_allow_html=True)
            
            with tab2:
                st.subheader("データ可視化")
                
                # Chart type selector
                chart_type = st.selectbox(
                    "チャートタイプ", 
                    [
                        "再生数 vs 登録者数", 
                        "上振れ係数ランキング", 
                        "24時間再生数ランキング",
                        "人気タグ分析",
                        "人気キーワード分析",
                        "投稿時間帯ヒートマップ"
                    ]
                )
                
                # すべてのチャートタイプで共通して実行するdf存在チェック
                if 'df' not in locals() or df is None or len(df) == 0:
                    st.warning("表示するデータがありません。検索条件を変更してください。")
                elif chart_type == "再生数 vs 登録者数":
                    df_chart = format_for_display(df)
                    df_chart['title_short'] = df_chart['title'].str[:30] + '...'
                    
                    # 改善された色調とデザインで散布図を作成
                    fig = px.scatter(
                        df_chart,
                        x='subscriber_count',
                        y='view_count',
                        size='engagement_ratio',
                        color='estimated_24h_views',
                        hover_name='title',
                        text='title_short',
                        log_x=True,
                        log_y=True,
                        size_max=35,
                        color_continuous_scale=px.colors.sequential.Viridis,
                        labels={
                            'subscriber_count': 'チャンネル登録者数',
                            'view_count': '再生回数',
                            'engagement_ratio': '上振れ係数',
                            'estimated_24h_views': '推定24時間再生数'
                        },
                    )
                    
                    # 改善されたグラフレイアウトとスタイル
                    fig.update_traces(
                        textposition='top center',
                        marker=dict(
                            line=dict(width=1, color='white'),
                            opacity=0.85,
                            sizemin=5,
                        ),
                        textfont=dict(family="Helvetica Neue, Arial", size=10)
                    )
                    
                    # グラフレイアウトの改善
                    fig.update_layout(
                        title={
                            'text': f"<b>再生数 vs 登録者数</b>",
                            'y': 0.95,
                            'x': 0.5,
                            'xanchor': 'center',
                            'yanchor': 'top',
                            'font': dict(family="Helvetica Neue, Arial", size=22, color="#2E3B4E")
                        },
                        height=600,
                        plot_bgcolor='rgba(255,255,255,0.95)',
                        paper_bgcolor='rgba(255,255,255,0)',
                        hovermode='closest',
                        legend=dict(title_font=dict(size=14), font=dict(size=12)),
                        xaxis=dict(
                            title=dict(font=dict(size=14)),
                            showgrid=True,
                            gridcolor='rgba(200,200,200,0.2)',
                            zeroline=False,
                            showline=True,
                            linewidth=1,
                            linecolor='rgba(200,200,200,0.6)',
                        ),
                        yaxis=dict(
                            title=dict(font=dict(size=14)),
                            showgrid=True,
                            gridcolor='rgba(200,200,200,0.2)',
                            zeroline=False,
                            showline=True,
                            linewidth=1,
                            linecolor='rgba(200,200,200,0.6)',
                        ),
                        coloraxis_colorbar=dict(
                            title="推定24時間\n再生数",
                            thicknessmode="pixels", thickness=20,
                            lenmode="pixels", len=300,
                            yanchor="top", y=1,
                            xanchor="left", x=1.02,
                            ticks="outside"
                        ),
                    )
                    
                    # チャートの下に説明を追加
                    st.plotly_chart(fig, use_container_width=True)
                    st.markdown("<div style='text-align: center; color: #666; font-style: italic; margin-top: -15px;'>バブルの大きさは上振れ係数、色は24時間推定再生数を表します</div>", unsafe_allow_html=True)
                    
                elif chart_type == "上振れ係数ランキング":
                    # Sort by engagement ratio
                    df_chart = df.sort_values('engagement_ratio', ascending=False).head(20)
                    
                    # 上振れ係数ランキングのための改善されたバーチャート
                    fig = px.bar(
                        df_chart,
                        x='engagement_ratio',
                        y='title',
                        orientation='h',
                        color='view_count',
                        color_continuous_scale=px.colors.sequential.Plasma,
                        labels={
                            'engagement_ratio': '上振れ係数 (再生数÷登録者数)',
                            'title': '動画タイトル',
                            'view_count': '再生回数'
                        },
                        text='engagement_ratio',  # 数値を表示
                    )
                    
                    # バーのスタイルを改善
                    fig.update_traces(
                        texttemplate='%{text:.2f}',  # 小数点2桁で表示
                        textposition='outside',
                        marker=dict(
                            line=dict(width=1, color='white'),
                        ),
                        textfont=dict(family="Helvetica Neue, Arial", size=10, color="#333")
                    )
                    
                    # レイアウトの洗練化
                    fig.update_layout(
                        title={
                            'text': f"<b>上振れ係数ランキング (トップ20)</b>",
                            'y': 0.95,
                            'x': 0.5,
                            'xanchor': 'center',
                            'yanchor': 'top',
                            'font': dict(family="Helvetica Neue, Arial", size=22, color="#2E3B4E")
                        },
                        height=600, 
                        plot_bgcolor='rgba(255,255,255,0.95)',
                        paper_bgcolor='rgba(255,255,255,0)',
                        hovermode='closest',
                        margin=dict(l=10, r=150, t=80, b=50),
                        xaxis=dict(
                            title=dict(font=dict(size=14)),
                            showgrid=True,
                            gridcolor='rgba(200,200,200,0.2)',
                            zeroline=False,
                            showline=True,
                            linewidth=1,
                            linecolor='rgba(200,200,200,0.6)',
                        ),
                        yaxis=dict(
                            categoryorder='total ascending',
                            title=dict(font=dict(size=14)),
                            showgrid=False,
                        ),
                        coloraxis_colorbar=dict(
                            title="再生回数",
                            thicknessmode="pixels", thickness=20,
                            lenmode="pixels", len=300,
                            yanchor="top", y=1,
                            xanchor="left", x=1.02,
                            ticks="outside"
                        ),
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    st.markdown("<div style='text-align: center; color: #666; font-style: italic; margin-top: -15px;'>登録者数に対して特に高い再生数を獲得している動画のランキングです</div>", unsafe_allow_html=True)
                    
                elif chart_type == "人気タグ分析":
                    # タグ分析器を初期化
                    analyzer = TagAnalyzer()
                    
                    with st.spinner('タグを分析中...'):
                        # セッションステートから動画データを取得
                        video_data = st.session_state.video_data
                        
                        # 人気タグを分析
                        top_tags, df_tags = analyzer.analyze_tags(video_data)
                        
                        # 結果が存在すれば表示
                        if top_tags and len(top_tags) > 0:
                            # 表示する件数を制限（上位15件）
                            limit = 15
                            df_display = df_tags.head(limit)
                            
                            # Plotlyで洗練されたグラフを作成
                            fig = px.bar(
                                df_display,
                                x='count',
                                y='tag',
                                orientation='h',
                                color='count',
                                color_continuous_scale=px.colors.sequential.Viridis,
                                labels={
                                    'count': '出現回数',
                                    'tag': 'タグ'
                                },
                                text='count'  # 数値を表示
                            )
                            
                            # バーのスタイルを改善
                            fig.update_traces(
                                texttemplate='%{text:.0f}',  # 整数表示
                                textposition='outside',
                                marker=dict(
                                    line=dict(width=1, color='white'),
                                ),
                                textfont=dict(family="Helvetica Neue, Arial", size=10, color="#333")
                            )
                            
                            # レイアウトの洗練化
                            fig.update_layout(
                                title={
                                    'text': f"<b>人気タグランキング (上位{limit}件)</b>",
                                    'y': 0.95,
                                    'x': 0.5,
                                    'xanchor': 'center',
                                    'yanchor': 'top',
                                    'font': dict(family="Helvetica Neue, Arial", size=22, color="#2E3B4E")
                                },
                                height=600,
                                plot_bgcolor='rgba(255,255,255,0.95)',
                                paper_bgcolor='rgba(255,255,255,0)',
                                hovermode='closest',
                                margin=dict(l=10, r=150, t=80, b=50),
                                xaxis=dict(
                                    title=dict(font=dict(size=14)),
                                    showgrid=True,
                                    gridcolor='rgba(200,200,200,0.2)',
                                    zeroline=False,
                                    showline=True,
                                    linewidth=1,
                                    linecolor='rgba(200,200,200,0.6)',
                                ),
                                yaxis=dict(
                                    categoryorder='total ascending',
                                    title=dict(font=dict(size=14)),
                                    showgrid=False,
                                ),
                                coloraxis_colorbar=dict(
                                    title="出現回数",
                                    thicknessmode="pixels", thickness=20,
                                    lenmode="pixels", len=300,
                                    yanchor="top", y=1,
                                    xanchor="left", x=1.02,
                                    ticks="outside"
                                ),
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                            st.markdown("<div style='text-align: center; color: #666; font-style: italic; margin-top: -15px;'>検索結果の動画に付けられた人気タグの出現頻度ランキング</div>", unsafe_allow_html=True)
                            
                            # テーブルでも表示
                            st.dataframe(
                                df_tags.rename(columns={'tag': 'タグ', 'count': '出現回数'}),
                                use_container_width=True,
                                hide_index=True
                            )
                        else:
                            st.warning("タグ情報が設定されている動画が見つかりませんでした。")
                
                elif chart_type == "人気キーワード分析":
                    # タグ分析器を初期化
                    analyzer = TagAnalyzer()
                    
                    with st.spinner('キーワードを分析中...'):
                        # セッションステートから動画データを取得
                        video_data = st.session_state.video_data
                        
                        # 分析対象フィールドを選択
                        field_options = st.multiselect(
                            "分析対象",
                            ["タイトル", "説明文"],
                            default=["タイトル", "説明文"]
                        )
                        
                        # 選択されたフィールドを英語フィールド名に変換
                        fields = []
                        if "タイトル" in field_options:
                            fields.append('title')
                        if "説明文" in field_options:
                            fields.append('description')
                        
                        # 人気キーワードを分析
                        top_keywords, df_keywords = analyzer.extract_keywords(video_data, fields)
                        
                        # 結果が存在すれば表示
                        if top_keywords and len(top_keywords) > 0:
                            # 表示する件数を制限（上位15件）
                            limit = 15
                            df_display = df_keywords.head(limit)
                            
                            # 選択したフィールドに基づいたサブタイトルを作成
                            source_text = ", ".join([option for option in field_options])
                            
                            # Plotlyで洗練されたグラフを作成
                            fig = px.bar(
                                df_display,
                                x='count',
                                y='keyword',
                                orientation='h',
                                color='count',
                                color_continuous_scale=px.colors.sequential.Plasma,  # タグ分析とやや異なるカラースケール
                                labels={
                                    'count': '出現回数',
                                    'keyword': 'キーワード'
                                },
                                text='count'  # 数値を表示
                            )
                            
                            # バーのスタイルを改善
                            fig.update_traces(
                                texttemplate='%{text:.0f}',  # 整数表示
                                textposition='outside',
                                marker=dict(
                                    line=dict(width=1, color='white'),
                                ),
                                textfont=dict(family="Helvetica Neue, Arial", size=10, color="#333")
                            )
                            
                            # レイアウトの洗練化
                            fig.update_layout(
                                title={
                                    'text': f"<b>人気キーワードランキング (上位{limit}件)</b>",
                                    'y': 0.95,
                                    'x': 0.5,
                                    'xanchor': 'center',
                                    'yanchor': 'top',
                                    'font': dict(family="Helvetica Neue, Arial", size=22, color="#2E3B4E")
                                },
                                height=600,
                                plot_bgcolor='rgba(255,255,255,0.95)',
                                paper_bgcolor='rgba(255,255,255,0)',
                                hovermode='closest',
                                margin=dict(l=10, r=150, t=80, b=50),
                                xaxis=dict(
                                    title=dict(font=dict(size=14)),
                                    showgrid=True,
                                    gridcolor='rgba(200,200,200,0.2)',
                                    zeroline=False,
                                    showline=True,
                                    linewidth=1,
                                    linecolor='rgba(200,200,200,0.6)',
                                ),
                                yaxis=dict(
                                    categoryorder='total ascending',
                                    title=dict(font=dict(size=14)),
                                    showgrid=False,
                                ),
                                coloraxis_colorbar=dict(
                                    title="出現回数",
                                    thicknessmode="pixels", thickness=20,
                                    lenmode="pixels", len=300,
                                    yanchor="top", y=1,
                                    xanchor="left", x=1.02,
                                    ticks="outside"
                                ),
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                            st.markdown(f"<div style='text-align: center; color: #666; font-style: italic; margin-top: -15px;'>分析対象: {source_text}から抽出した人気キーワードの出現頻度</div>", unsafe_allow_html=True)
                            
                            # テーブルでも表示
                            st.dataframe(
                                df_keywords.rename(columns={'keyword': 'キーワード', 'count': '出現回数'}),
                                use_container_width=True,
                                hide_index=True
                            )
                        else:
                            st.warning("キーワードが抽出できませんでした。")
                
                elif chart_type == "投稿時間帯ヒートマップ":
                    # 時間帯分析器を初期化
                    time_analyzer = TimeAnalyzer()
                    
                    with st.spinner('投稿時間帯を分析中...'):
                        # セッションステートから動画データを取得
                        video_data = st.session_state.video_data
                        
                        # 投稿時間データを抽出
                        time_df = time_analyzer.extract_time_data(video_data)
                        
                        if not time_df.empty:
                            # 曜日×時間のピボットテーブル作成
                            pivot_count = pd.crosstab(time_df['day_name'], time_df['hour_str'])
                            
                            # 曜日を月曜から日曜の順に並べ替え
                            days_jp = ['月', '火', '水', '木', '金', '土', '日']
                            pivot_count = pivot_count.reindex(days_jp)
                            
                            # 再生数ピボット
                            pivot_views = time_df.pivot_table(
                                values='view_count', 
                                index='day_name', 
                                columns='hour_str', 
                                aggfunc='mean'
                            )
                            pivot_views = pivot_views.reindex(days_jp)
                            
                            # データの準備
                            # ヒートマップ用に動画本数データを整形
                            count_df = pivot_count.reset_index()
                            count_df = pd.melt(count_df, id_vars='day_name', var_name='hour', value_name='count')
                            
                            # ヒートマップ用に再生数データを整形
                            views_df = pivot_views.reset_index()
                            views_df = pd.melt(views_df, id_vars='day_name', var_name='hour', value_name='views')
                            
                            # 1. 投稿数ヒートマップの作成
                            fig_count = px.imshow(
                                pivot_count,
                                labels=dict(x="時間帯", y="曜日", color="投稿数"),
                                x=pivot_count.columns.tolist(),
                                y=days_jp,
                                color_continuous_scale='YlGnBu',
                                aspect="auto",
                                text_auto=True
                            )
                            
                            fig_count.update_layout(
                                title={
                                    'text': "<b>人気動画の投稿時間帯 (投稿数)</b>",
                                    'y': 0.95,
                                    'x': 0.5,
                                    'xanchor': 'center',
                                    'yanchor': 'top',
                                    'font': dict(family="Helvetica Neue, Arial", size=20, color="#2E3B4E")
                                },
                                height=450,
                                paper_bgcolor='rgba(255,255,255,0)',
                                plot_bgcolor='rgba(255,255,255,0.9)',
                                coloraxis_showscale=True,
                                margin=dict(l=50, r=50, t=80, b=30),
                                coloraxis_colorbar=dict(
                                    title="投稿数",
                                    thicknessmode="pixels", thickness=20,
                                    lenmode="pixels", len=300,
                                    yanchor="top", y=1,
                                    xanchor="left", x=1.02,
                                    ticks="outside"
                                ),
                            )
                            
                            # グリッド線を追加
                            fig_count.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(200,200,200,0.2)', title_font=dict(size=14))
                            fig_count.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(200,200,200,0.2)', title_font=dict(size=14))
                            
                            # グラフを表示
                            st.plotly_chart(fig_count, use_container_width=True)
                            st.markdown("<div style='text-align: center; color: #666; font-style: italic; margin-top: -15px;'>人気動画の曜日×時間帯別の投稿数進陣変化を表示</div>", unsafe_allow_html=True)
                            
                            # 2. 再生数ヒートマップの作成
                            fig_views = px.imshow(
                                pivot_views,
                                labels=dict(x="時間帯", y="曜日", color="平均再生数"),
                                x=pivot_views.columns.tolist(),
                                y=days_jp,
                                color_continuous_scale='YlOrRd',
                                aspect="auto",
                                text_auto='.0f'  # 整数表示
                            )
                            
                            fig_views.update_layout(
                                title={
                                    'text': "<b>人気動画の投稿時間帯 (平均再生数)</b>",
                                    'y': 0.95,
                                    'x': 0.5,
                                    'xanchor': 'center',
                                    'yanchor': 'top',
                                    'font': dict(family="Helvetica Neue, Arial", size=20, color="#2E3B4E")
                                },
                                height=450,
                                paper_bgcolor='rgba(255,255,255,0)',
                                plot_bgcolor='rgba(255,255,255,0.9)',
                                coloraxis_showscale=True,
                                margin=dict(l=50, r=50, t=80, b=30),
                                coloraxis_colorbar=dict(
                                    title="平均再生数",
                                    thicknessmode="pixels", thickness=20,
                                    lenmode="pixels", len=300,
                                    yanchor="top", y=1,
                                    xanchor="left", x=1.02,
                                    ticks="outside"
                                ),
                            )
                            
                            # グリッド線を追加
                            fig_views.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(200,200,200,0.2)', title_font=dict(size=14))
                            fig_views.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(200,200,200,0.2)', title_font=dict(size=14))
                            
                            # グラフを表示
                            st.plotly_chart(fig_views, use_container_width=True)
                            st.markdown("<div style='text-align: center; color: #666; font-style: italic; margin-top: -15px;'>人気動画の曜日×時間帯別の平均再生数を表示</div>", unsafe_allow_html=True)
                            
                            # 投稿時間データの統計情報を表示
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                # 最も投稿が多い曜日
                                day_counts = time_df['day_name'].value_counts()
                                most_common_day = day_counts.index[0]
                                st.metric("投稿が最も多い曜日", f"{most_common_day}曜日 ({day_counts.iloc[0]}件)")
                            
                            with col2:
                                # 最も投稿が多い時間帯
                                hour_counts = time_df['hour_str'].value_counts()
                                most_common_hour = hour_counts.index[0]
                                st.metric("投稿が最も多い時間帯", f"{most_common_hour} ({hour_counts.iloc[0]}件)")
                            
                            # 投稿時間データの詳細を表示
                            with st.expander("投稿時間データの詳細", expanded=False):
                                st.dataframe(
                                    time_df[['title', 'day_name', 'hour_str', 'view_count']].rename(
                                        columns={
                                            'title': '動画タイトル', 
                                            'day_name': '曜日', 
                                            'hour_str': '時間帯',
                                            'view_count': '再生回数'
                                        }
                                    ),
                                    use_container_width=True
                                )
                        else:
                            st.warning("投稿時間データを抽出できませんでした。")
                    
                elif chart_type == "24時間再生数ランキング":
                    # Sort by estimated 24h views
                    df_chart = df.sort_values('estimated_24h_views', ascending=False).head(20)
                    
                    if df_chart['estimated_24h_views'].sum() > 0:
                        # 改善された24時間再生数ランキングのバーチャート
                        fig = px.bar(
                            df_chart,
                            x='estimated_24h_views',
                            y='title',
                            orientation='h',
                            color='view_count',
                            color_continuous_scale=px.colors.sequential.Teal,
                            labels={
                                'estimated_24h_views': '推定24時間再生数',
                                'title': '動画タイトル',
                                'view_count': '総再生回数'
                            },
                            text='estimated_24h_views',  # 数値を表示
                        )
                        
                        # バーのスタイルを改善
                        fig.update_traces(
                            texttemplate='%{text:,.0f}',  # カンマ区切りで数値表示
                            textposition='outside',
                            marker=dict(
                                line=dict(width=1, color='white'),
                            ),
                            textfont=dict(family="Helvetica Neue, Arial", size=10, color="#333")
                        )
                        
                        # レイアウトの洗練化
                        fig.update_layout(
                            title={
                                'text': f"<b>推定24時間再生数ランキング (トップ20)</b>",
                                'y': 0.95,
                                'x': 0.5,
                                'xanchor': 'center',
                                'yanchor': 'top',
                                'font': dict(family="Helvetica Neue, Arial", size=22, color="#2E3B4E")
                            },
                            height=600, 
                            plot_bgcolor='rgba(255,255,255,0.95)',
                            paper_bgcolor='rgba(255,255,255,0)',
                            hovermode='closest',
                            margin=dict(l=10, r=150, t=80, b=50),
                            xaxis=dict(
                                title=dict(font=dict(size=14)),
                                showgrid=True,
                                gridcolor='rgba(200,200,200,0.2)',
                                zeroline=False,
                                showline=True,
                                linewidth=1,
                                linecolor='rgba(200,200,200,0.6)',
                            ),
                            yaxis=dict(
                                categoryorder='total ascending',
                                title=dict(font=dict(size=14)),
                                showgrid=False,
                            ),
                            coloraxis_colorbar=dict(
                                title="総再生回数",
                                thicknessmode="pixels", thickness=20,
                                lenmode="pixels", len=300,
                                yanchor="top", y=1,
                                xanchor="left", x=1.02,
                                ticks="outside"
                            ),
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                        st.markdown("<div style='text-align: center; color: #666; font-style: italic; margin-top: -15px;'>投稿から24時間での推定再生数を総再生数で色分けして表示</div>", unsafe_allow_html=True)
                    else:
                        st.info("24時間再生数のデータが不足しています。前回のデータと比較するには、定期実行またはGoogleスプレッドシートの履歴が必要です。")
            
            with tab3:
                st.subheader("動画詳細情報")
                
                # dfが存在し、データがあるか確認
                if 'df' in locals() and df is not None and len(df) > 0:
                    # Filter by channel
                    channels = df['channel_name'].unique()
                    selected_channel = st.selectbox("チャンネルで絞り込み", ['すべて表示'] + list(channels))
                    
                    filtered_df = df if selected_channel == 'すべて表示' else df[df['channel_name'] == selected_channel]
                    
                    # Display videos as cards
                    for i, video in filtered_df.iterrows():
                        with st.expander(f"{video['title']}"):
                            col1, col2 = st.columns([1, 2])
                            
                            with col1:
                                # Display video thumbnail
                                st.image(f"https://img.youtube.com/vi/{video['video_id']}/mqdefault.jpg")
                                st.markdown(f"[YouTubeで視聴](https://www.youtube.com/watch?v={video['video_id']})")
                            
                            with col2:
                                st.markdown(f"**チャンネル名:** {video['channel_name']}")
                                st.markdown(f"**投稿日:** {video['published_at']}")
                                st.markdown(f"**再生回数:** {video['view_count']:,}")
                                
                                if 'estimated_24h_views' in video and video['estimated_24h_views'] > 0:
                                    st.markdown(f"**推定24時間再生数:** {video['estimated_24h_views']:,}")
                                
                                st.markdown(f"**高評価数:** {video['like_count']:,}")
                                st.markdown(f"**コメント数:** {video['comment_count']:,}")
                                st.markdown(f"**チャンネル登録者数:** {video['subscriber_count']:,}")
                                st.markdown(f"**上振れ係数:** {video['engagement_ratio']:.2f}")
                                
                                if 'tags' in video and video['tags']:
                                    st.markdown(f"**タグ:** {', '.join(video['tags'])}")
                                    
                                st.markdown("**説明:**")
                                st.text(video.get('description', '説明なし'))
                else:
                    st.warning("表示するデータがありません。検索条件を変更してください。")
            
            with tab4:
                st.subheader("競合チャンネル比較分析")
                
                # チャンネルアナライザーの初期化
                channel_analyzer = ChannelAnalyzer()
                youtube_client = YouTubeDataAPI(api_key)
                
                # チャンネルIDの入力
                st.write("複数のチャンネルIDをカンマ区切りで入力して比較分析します")
                channel_ids_input = st.text_area(
                    "チャンネルIDを入力 (カンマ区切り)",
                    placeholder="例: UC1234567890,UC0987654321,UC1122334455",
                    key="channel_comparison_ids_main"
                )
                
                # 検索結果から自動的にチャンネルIDを追加するオプション
                st.write("または検索結果から自動的にチャンネルを追加:")
                
                # dfが存在し、データがあるか確認
                if 'df' in locals() and df is not None and len(df) > 0 and 'channel_id' in df.columns:
                    unique_channels = df[['channel_name', 'channel_id']].drop_duplicates()
                    if not unique_channels.empty:
                        channel_options = {row['channel_name']: row['channel_id'] for _, row in unique_channels.iterrows()}
                        selected_channels = st.multiselect(
                            "検索結果からチャンネルを選択",
                            options=list(channel_options.keys())
                        )
                        
                        # 選択されたチャンネルIDを取得
                        selected_ids = [channel_options[name] for name in selected_channels]
                        
                        # 既存の入力と結合
                        if channel_ids_input.strip() and selected_ids:
                            existing_ids = [cid.strip() for cid in channel_ids_input.split(',') if cid.strip()]
                            all_ids = list(set(existing_ids + selected_ids))  # 重複を除去
                            channel_ids_input = ','.join(all_ids)
                            st.session_state.channel_comparison_ids_main = channel_ids_input
                        elif selected_ids:
                            channel_ids_input = ','.join(selected_ids)
                            st.session_state.channel_comparison_ids_main = channel_ids_input
                
                if st.button("チャンネルを分析", key="analyze_channels_btn_main"):
                    if channel_ids_input.strip():
                        with st.spinner("チャンネルデータを取得中..."):
                            # チャンネルIDをリストに変換
                            channel_ids = [cid.strip() for cid in channel_ids_input.split(',') if cid.strip()]
                            
                            if len(channel_ids) > 0:
                                # チャンネルデータを取得
                                channel_details = channel_analyzer.fetch_channel_stats(youtube_client, channel_ids)
                                
                                if channel_details:
                                    # チャンネルデータを比較可能な形式に変換
                                    df_channels = channel_analyzer.compare_channels(channel_details)
                                    
                                    if not df_channels.empty:
                                        # チャンネル基本情報を表示
                                        st.subheader("チャンネル基本情報")
                                        df_display = df_channels[[
                                            'channel_name', 'subscriber_count', 'video_count', 'view_count', 
                                            'avg_views_per_video', 'engagement_ratio', 'videos_per_month'
                                        ]].rename(columns={
                                            'channel_name': 'チャンネル名',
                                            'subscriber_count': '登録者数',
                                            'video_count': '動画数',
                                            'view_count': '総再生数',
                                            'avg_views_per_video': '動画平均再生数',
                                            'engagement_ratio': 'エンゲージメント率(%)',
                                            'videos_per_month': '月間投稿数'
                                        })
                                        
                                        # 表形式でデータを表示
                                        st.dataframe(
                                            df_display.style.format({
                                                '登録者数': '{:,.0f}',
                                                '動画数': '{:,.0f}',
                                                '総再生数': '{:,.0f}',
                                                '動画平均再生数': '{:,.0f}',
                                                'エンゲージメント率(%)': '{:.2f}',
                                                '月間投稿数': '{:.1f}'
                                            }),
                                            use_container_width=True
                                        )
                                        
                                        # 比較チャートを生成して表示
                                        st.subheader("チャンネル比較チャート")
                                        figures = channel_analyzer.create_comparison_charts(df_channels)
                                        
                                        for i, fig in enumerate(figures):
                                            st.pyplot(fig)
                                    else:
                                        st.warning("チャンネルデータを比較形式に変換できませんでした。")
                                else:
                                    st.error("チャンネルデータの取得に失敗しました。チャンネルIDが正しいか確認してください。")
                            else:
                                st.warning("有効なチャンネルIDが入力されていません。")
                    else:
                        st.warning("チャンネルIDを入力してください。")
                
                # チャンネルIDの見つけ方を表示
                with st.expander("チャンネルIDの見つけ方", expanded=False):
                    st.write("""
                    YouTubeチャンネルIDを見つける方法：
                    1. YouTubeでチャンネルページに移動する
                    2. URLを確認する
                        - 形式1: `https://www.youtube.com/channel/UC...` の場合、UC以降の文字列がチャンネルID
                        - 形式2: `https://www.youtube.com/c/チャンネル名` の場合は、「詳細」→「共有」→「チャンネルID」で確認
                    3. または検索結果から目的のチャンネルを選び、URLからチャンネルIDを取得
                    
                    例: UCQFgXJimhOt-MvfFLgNvnNQ（サンプルID）
                    """)
                    st.info("注：チャンネルID比較は多くのAPI使用量を消費します。一度に分析するチャンネル数は5つ程度までが推奨です。")
                    
            with tab5:
                st.subheader("キーワード比較分析")
                
                # キーワード分析オブジェクトの初期化
                keyword_analyzer = KeywordAnalyzer()
                
                # キーワード比較機能の実装
                if 'keywords_data' in st.session_state and len(st.session_state.keywords_data) > 1:
                    # 複数キーワードがある場合
                    keywords = list(st.session_state.keywords_data.keys())
                    
                    st.write(f"{len(keywords)}個のキーワードを比較します")
                    
                    # 比較タイプの選択
                    comparison_type = st.radio(
                        "比較タイプ",
                        ["概要比較", "再生数比較", "エンゲージメント比較", "コメント比較"],
                        horizontal=True
                    )
                    
                    # 各キーワードの統計情報を計算
                    stats_df = keyword_analyzer.compare_keywords_stats(st.session_state.keywords_data)
                    
                    if not stats_df.empty:
                        # 統計情報を表示
                        st.subheader("キーワード比較統計")
                        
                        # 表示列を選択
                        if comparison_type == "概要比較":
                            display_cols = ['キーワード', '動画数', '平均再生数', '平均上振れ係数']
                        elif comparison_type == "再生数比較":
                            display_cols = ['キーワード', '動画数', '平均再生数', '最大再生数', '中央値再生数']
                        elif comparison_type == "エンゲージメント比較":
                            display_cols = ['キーワード', '平均上振れ係数', '平均高評価率', '平均動画長(秒)']
                        elif comparison_type == "コメント比較":
                            display_cols = ['キーワード', '平均コメント数', '平均コメント率']
                        
                        # 利用可能な列のみを表示
                        available_cols = [col for col in display_cols if col in stats_df.columns]
                        
                        if available_cols:
                            # データをフォーマットして表示
                            formatted_df = keyword_analyzer.format_stats_df(stats_df[available_cols])
                            st.dataframe(formatted_df, use_container_width=True)
                            
                            # 棒グラフでキーワード比較を表示
                            st.subheader("キーワード比較グラフ")
                            
                            # グラフ表示列を選択
                            numeric_cols = [col for col in stats_df.columns if col != 'キーワード']
                            selected_metric = st.selectbox("表示指標", numeric_cols)
                            
                            if selected_metric in stats_df.columns:
                                # グラフ作成
                                fig = keyword_analyzer.create_comparison_charts(stats_df, selected_metric)
                                if fig is not None:
                                    st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.warning("利用可能な列がありません。")
                    else:
                        st.warning("比較できるデータがありません。")
                else:
                    st.info("複数のキーワードを検索してください。カンマ区切りまたは改行で複数のキーワードを入力できます。")
                    
                    # 複数キーワードの入力方法を説明
                    with st.expander("複数キーワードの入力方法"):
                        st.markdown("""
                        ### 複数キーワードの入力方法
                        
                        検索フォームに複数のキーワードを入力する方法は2つあります：
                        
                        1. **カンマ区切り**で入力する方法：
                           ```
                           筆トレ,ノートテイキング,勉強法
                           ```
                        
                        2. **改行**で入力する方法：
                           ```
                           筆トレ
                           ノートテイキング
                           勉強法
                           ```
                        
                        検索すると、各キーワードの検索結果を比較分析できます。
                        キーワード比較タブで平均再生数やエンゲージメント率などを比較できます。
                        """)

    else:
        # Initial state - show instructions
        st.info("サイドバーで検索条件を入力し、「検索」ボタンをクリックしてください。")
        
        # How to use guide
        with st.expander("使い方ガイド"):
            st.markdown("""
            ### このツールについて
            YouTube Data APIを使用して、指定したキーワードに関連する人気動画を検索し、そのデータを分析するツールです。
            
            ### 主な機能
            
            1. **キーワード検索**: 任意のキーワードでYouTube動画を検索（最大50件）
            2. **データ表示**: 動画タイトル、チャンネル名、再生数、高評価数などの情報を表示
            3. **チャンネル情報**: チャンネル登録者数を取得し、上振れ係数（再生数÷登録者数）を計算
            4. **データ可視化**: 様々なチャートで動画データを可視化
            5. **24時間再生数推定**: 前回保存された再生数との差分から、推定24時間再生数を計算
            6. **CSVエクスポート**: 取得したデータをCSVでダウンロード可能
            
            ### 設定方法
            
            1. YouTube Data APIキーを取得し、サイドバーに入力するか環境変数に設定
            2. Google Sheets APIを使用するには、サービスアカウント認証情報が必要です
            
            ### 制限事項
            
            - YouTube APIのQuota制限（1日あたり10,000ポイント）に注意してください
            - 推定24時間再生数は、前回のデータが保存されている場合のみ表示されます
            """)

if __name__ == '__main__':
    main()
