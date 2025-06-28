import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
# 日本語フォントの設定 (japanize_matplotlibの代わり)
try:
    import matplotlib
    matplotlib.rc('font', family='IPAGothic')  # IPAフォントを指定
except:
    # フォント設定に失敗しても続行
    print('日本語フォント設定に失敗しました。日本語が正しく表示されない可能性があります。')
import seaborn as sns
from datetime import datetime
from typing import Dict, List, Any, Tuple

class TimeAnalyzer:
    """YouTubeの投稿時間帯を分析するクラス"""
    
    def __init__(self):
        """初期化"""
        # 曜日の日本語表記
        self.days_jp = ['月', '火', '水', '木', '金', '土', '日']
        # 時間帯の表記
        self.hours = [f"{h}時" for h in range(24)]

    def extract_time_data(self, videos_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        動画データから投稿時間帯情報を抽出
        
        Args:
            videos_data: 動画データのリスト
            
        Returns:
            時間帯データを含むDataFrame
        """
        # 時間データ保存用の配列
        times_data = []
        
        for video in videos_data:
            # 投稿日時を取得
            published_at = video.get('published_at', '')
            
            # ISO形式の日時文字列を解析
            try:
                if isinstance(published_at, str) and published_at.strip():
                    # 日付形式を確認
                    if 'T' in published_at or ' ' in published_at:  # ISO形式または標準形式
                        # 'Z'が含まれていたらUTCからJST(+9時間)に変換
                        if 'Z' in published_at:
                            dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                            # UTC→JST変換（+9時間）
                            dt = dt.replace(tzinfo=None) + pd.Timedelta(hours=9)
                        else:
                            # すでに現地時間と仮定
                            dt = datetime.fromisoformat(published_at)
                    else:
                        # 日付のみの場合は時間を0時とする
                        dt = datetime.strptime(published_at, '%Y-%m-%d')
                        
                    # 結果を辞書で保存
                    times_data.append({
                        'video_id': video.get('video_id', ''),
                        'title': video.get('title', ''),
                        'day_of_week': dt.weekday(),  # 月曜=0, 日曜=6
                        'hour': dt.hour,
                        'day_name': self.days_jp[dt.weekday()],
                        'hour_str': f"{dt.hour}時",
                        'view_count': video.get('view_count', 0)
                    })
            except (ValueError, TypeError) as e:
                # 日付解析エラーは無視
                pass
                
        # DataFrameに変換
        return pd.DataFrame(times_data) if times_data else pd.DataFrame()
    
    def create_heatmap(self, df: pd.DataFrame, title: str = "投稿時間帯ヒートマップ") -> Tuple[plt.Figure, plt.Axes]:
        """
        投稿時間帯のヒートマップを作成
        
        Args:
            df: 時間帯データを含むDataFrame
            title: グラフタイトル
            
        Returns:
            matplotlib図とaxes
        """
        if df.empty:
            # データがない場合は空の図を返す
            fig, ax = plt.subplots(figsize=(12, 8))
            ax.text(0.5, 0.5, "データがありません", ha='center', va='center', fontsize=14)
            return fig, ax
            
        # dfが存在し、データがあるか確認
        if df is None or len(df) == 0:
            # データが無い場合は空のグラフを返す
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.text(0.5, 0.5, "表示するデータがありません", ha='center', va='center', fontsize=14)
            return fig, ax
        
        # 曼日×時間のピボットテーブル作成
        # 集計方法: カウント（デフォルト）と平均再生数の2種類
        pivot_count = pd.crosstab(df['day_name'], df['hour_str'])
        
        # 曜日を月曜から日曜の順に並べ替え
        pivot_count = pivot_count.reindex(self.days_jp)
        
        # 再生数ピボット
        if df is not None and len(df) > 0 and 'view_count' in df.columns:
            pivot_views = df.pivot_table(
                values='view_count', 
                index='day_name', 
                columns='hour_str', 
                aggfunc='mean'
            )
            pivot_views = pivot_views.reindex(self.days_jp)
        else:
            pivot_views = None
            
        # ヒートマップの作成
        fig, axes = plt.subplots(2 if pivot_views is not None else 1, 1, 
                              figsize=(14, 10 if pivot_views is not None else 6),
                              constrained_layout=True)
        
        if pivot_views is not None:
            ax1, ax2 = axes
        else:
            ax1 = axes
            
        # 投稿数ヒートマップ
        sns.heatmap(pivot_count, annot=True, fmt="d", cmap="YlGnBu", 
                   linewidths=.5, ax=ax1, cbar_kws={'label': '投稿数'})
        ax1.set_title(f"{title} (投稿数)", fontsize=14)
        ax1.set_xlabel('時間帯', fontsize=12)
        ax1.set_ylabel('曜日', fontsize=12)
        
        # 再生数ヒートマップ
        if pivot_views is not None:
            sns.heatmap(pivot_views, annot=True, fmt=".0f", cmap="YlOrRd", 
                       linewidths=.5, ax=ax2, cbar_kws={'label': '平均再生数'})
            ax2.set_title(f"{title} (平均再生数)", fontsize=14)
            ax2.set_xlabel('時間帯', fontsize=12)
            ax2.set_ylabel('曜日', fontsize=12)
        
        return fig, axes

# 単体テスト用
if __name__ == "__main__":
    # サンプルデータ
    test_data = [
        {
            'video_id': '123',
            'title': 'テスト動画1',
            'published_at': '2023-06-20T12:30:00Z',  # UTC時間
            'view_count': 1000
        },
        {
            'video_id': '456',
            'title': 'テスト動画2',
            'published_at': '2023-06-21T18:45:00Z',
            'view_count': 2000
        }
    ]
    
    analyzer = TimeAnalyzer()
    df = analyzer.extract_time_data(test_data)
    print(df)
    
    fig, _ = analyzer.create_heatmap(df)
    plt.show()
