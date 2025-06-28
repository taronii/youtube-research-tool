import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import japanize_matplotlib
import seaborn as sns
from typing import Dict, List, Any, Optional, Tuple
from dateutil.parser import parse as date_parse
from datetime import datetime, timedelta
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ChannelAnalyzer:
    """
    YouTubeチャンネル分析のためのクラス
    複数チャンネルの比較や統計情報の可視化を行う
    """
    
    def __init__(self):
        """初期化"""
        pass
    
    def fetch_channel_stats(self, youtube_client, channel_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        指定されたチャンネルIDのチャンネル統計情報を取得する
        
        Args:
            youtube_client: YouTubeDataAPIクライアント
            channel_ids: チャンネルIDのリスト
            
        Returns:
            チャンネルID -> 詳細情報のディクショナリ
        """
        if not channel_ids:
            return {}
            
        try:
            # チャンネル情報を取得
            channel_details = youtube_client.get_channel_details(channel_ids)
            
            # 各チャンネルの最新動画を取得
            for channel_id, details in channel_details.items():
                # 最新動画5件を取得
                latest_videos = youtube_client.get_latest_videos_for_channel(channel_id, 5)
                if latest_videos:
                    # チャンネル詳細に最新動画情報を追加
                    details['latest_videos'] = latest_videos
                    
                    # 平均統計情報を計算
                    avg_views = sum(v.get('statistics', {}).get('viewCount', 0) 
                              for v in latest_videos if v.get('statistics')) / max(len(latest_videos), 1)
                    avg_likes = sum(v.get('statistics', {}).get('likeCount', 0) 
                               for v in latest_videos if v.get('statistics')) / max(len(latest_videos), 1)
                    avg_comments = sum(v.get('statistics', {}).get('commentCount', 0) 
                                 for v in latest_videos if v.get('statistics')) / max(len(latest_videos), 1)
                    
                    details['avg_stats'] = {
                        'avg_views': int(avg_views),
                        'avg_likes': int(avg_likes),
                        'avg_comments': int(avg_comments)
                    }
                    
                    # 動画投稿ペースを計算
                    if len(latest_videos) >= 2:
                        publish_dates = []
                        for video in latest_videos:
                            snippet = video.get('snippet', {})
                            published_at = snippet.get('publishedAt')
                            if published_at:
                                try:
                                    publish_dates.append(date_parse(published_at))
                                except:
                                    pass
                        
                        if len(publish_dates) >= 2:
                            # 日付でソート
                            publish_dates.sort(reverse=True)
                            
                            # 平均間隔を計算（日数）
                            intervals = [(publish_dates[i] - publish_dates[i+1]).days 
                                        for i in range(len(publish_dates)-1)]
                            avg_interval = sum(intervals) / len(intervals)
                            
                            details['posting_pace'] = {
                                'avg_days_between_videos': round(avg_interval, 1),
                                'videos_per_month': round(30 / max(avg_interval, 1), 1)
                            }
            
            return channel_details
            
        except Exception as e:
            logger.error(f"チャンネル統計情報の取得中にエラーが発生しました: {e}")
            return {}
    
    def compare_channels(self, channel_details: Dict[str, Dict[str, Any]]) -> pd.DataFrame:
        """
        複数チャンネルの統計を比較可能なDataFrameに変換
        
        Args:
            channel_details: チャンネル詳細情報のディクショナリ
            
        Returns:
            比較用のDataFrame
        """
        comparison_data = []
        
        for channel_id, details in channel_details.items():
            # チャンネル基本情報
            snippet = details.get('snippet', {})
            statistics = details.get('statistics', {})
            
            # 1動画あたりの平均統計
            avg_stats = details.get('avg_stats', {})
            
            # 投稿ペース
            posting_pace = details.get('posting_pace', {})
            
            # データを整形
            channel_data = {
                'channel_id': channel_id,
                'channel_name': snippet.get('title', '不明'),
                'description': snippet.get('description', '')[:100] + '...' if snippet.get('description', '') else '',
                'subscriber_count': int(statistics.get('subscriberCount', 0)),
                'video_count': int(statistics.get('videoCount', 0)),
                'view_count': int(statistics.get('viewCount', 0)),
                'avg_views_per_video': int(statistics.get('viewCount', 0)) / max(int(statistics.get('videoCount', 1)), 1),
                'avg_views': avg_stats.get('avg_views', 0),
                'avg_likes': avg_stats.get('avg_likes', 0),
                'avg_comments': avg_stats.get('avg_comments', 0),
                'engagement_ratio': avg_stats.get('avg_likes', 0) / max(avg_stats.get('avg_views', 1), 1) * 100,
                'videos_per_month': posting_pace.get('videos_per_month', 0),
                'days_between_videos': posting_pace.get('avg_days_between_videos', 0),
                'created_at': snippet.get('publishedAt', ''),
            }
            
            comparison_data.append(channel_data)
        
        # DataFrameに変換
        return pd.DataFrame(comparison_data) if comparison_data else pd.DataFrame()
    
    def create_comparison_charts(self, df: pd.DataFrame) -> List[plt.Figure]:
        """
        チャンネル比較用のチャートを作成
        
        Args:
            df: チャンネル比較データ
            
        Returns:
            matplotlib図のリスト
        """
        # dfが存在し、データがあるかの完全なガード条件
        if df is None or df.empty or len(df) < 1:
            return []
            
        figures = []
        
        # 1. チャンネル登録者数比較
        fig1, ax1 = plt.subplots(figsize=(10, 6))
        sns.barplot(x='channel_name', y='subscriber_count', data=df, ax=ax1)
        ax1.set_title('チャンネル登録者数比較')
        ax1.set_xlabel('チャンネル名')
        ax1.set_ylabel('登録者数')
        ax1.tick_params(axis='x', rotation=45)
        
        # 値を表示
        for p in ax1.patches:
            ax1.annotate(f'{int(p.get_height()):,}', 
                       (p.get_x() + p.get_width() / 2., p.get_height()), 
                       ha = 'center', va = 'bottom', xytext = (0, 5), 
                       textcoords = 'offset points')
        
        fig1.tight_layout()
        figures.append(fig1)
        
        # 2. 平均再生数と平均エンゲージメント率
        fig2, ax2 = plt.subplots(figsize=(12, 6))
        
        # 左軸：平均再生数
        bars = sns.barplot(x='channel_name', y='avg_views', data=df, ax=ax2, color='royalblue', 
                         label='平均再生数')
        ax2.set_title('平均再生数とエンゲージメント比較')
        ax2.set_xlabel('チャンネル名')
        ax2.set_ylabel('平均再生数')
        
        # 値を表示
        for p in ax2.patches:
            ax2.annotate(f'{int(p.get_height()):,}', 
                       (p.get_x() + p.get_width() / 2., p.get_height()), 
                       ha = 'center', va = 'bottom', xytext = (0, 5), 
                       textcoords = 'offset points')
        
        # 右軸：エンゲージメント率
        ax3 = ax2.twinx()
        line = sns.lineplot(x='channel_name', y='engagement_ratio', data=df, ax=ax3, 
                          color='tomato', marker='o', label='エンゲージメント率')
        ax3.set_ylabel('エンゲージメント率 (%)')
        
        # 値を表示
        for i, v in enumerate(df['engagement_ratio']):
            ax3.annotate(f'{v:.2f}%', 
                       (i, v), 
                       ha = 'center', va = 'bottom', xytext = (0, 5), 
                       textcoords = 'offset points', color='tomato')
        
        # 凡例を表示
        lines, labels = ax2.get_legend_handles_labels()
        lines2, labels2 = ax3.get_legend_handles_labels()
        ax2.legend(lines + lines2, labels + labels2, loc='upper left')
        
        ax2.tick_params(axis='x', rotation=45)
        fig2.tight_layout()
        figures.append(fig2)
        
        # 3. 投稿ペース比較
        fig3, ax4 = plt.subplots(figsize=(10, 6))
        sns.barplot(x='channel_name', y='videos_per_month', data=df, ax=ax4, palette='viridis')
        ax4.set_title('月間平均投稿本数')
        ax4.set_xlabel('チャンネル名')
        ax4.set_ylabel('月間投稿本数')
        ax4.tick_params(axis='x', rotation=45)
        
        # 値を表示
        for p in ax4.patches:
            ax4.annotate(f'{p.get_height():.1f}', 
                       (p.get_x() + p.get_width() / 2., p.get_height()), 
                       ha = 'center', va = 'bottom', xytext = (0, 5), 
                       textcoords = 'offset points')
        
        fig3.tight_layout()
        figures.append(fig3)
        
        return figures

# 単体テスト用
if __name__ == "__main__":
    # サンプルデータ
    test_data = {
        'UC123456': {
            'snippet': {
                'title': 'サンプルチャンネル1',
                'description': 'これはサンプルチャンネル1の説明です',
                'publishedAt': '2020-01-01T00:00:00Z'
            },
            'statistics': {
                'subscriberCount': '10000',
                'videoCount': '100',
                'viewCount': '1000000'
            },
            'avg_stats': {
                'avg_views': 5000,
                'avg_likes': 300,
                'avg_comments': 50
            },
            'posting_pace': {
                'avg_days_between_videos': 3.5,
                'videos_per_month': 8.5
            }
        },
        'UC789012': {
            'snippet': {
                'title': 'サンプルチャンネル2',
                'description': 'これはサンプルチャンネル2の説明です',
                'publishedAt': '2019-01-01T00:00:00Z'
            },
            'statistics': {
                'subscriberCount': '20000',
                'videoCount': '200',
                'viewCount': '2000000'
            },
            'avg_stats': {
                'avg_views': 8000,
                'avg_likes': 500,
                'avg_comments': 100
            },
            'posting_pace': {
                'avg_days_between_videos': 7.0,
                'videos_per_month': 4.3
            }
        }
    }
    
    analyzer = ChannelAnalyzer()
    df = analyzer.compare_channels(test_data)
    print(df)
    
    figures = analyzer.create_comparison_charts(df)
    for fig in figures:
        plt.figure(fig.number)
        plt.show()
