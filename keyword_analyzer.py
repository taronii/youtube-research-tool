"""
キーワード分析用のヘルパー関数を提供するモジュール
複数キーワードの比較・分析のための機能を実装
"""

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Any, Optional, Tuple

class KeywordAnalyzer:
    """キーワード分析のためのクラス"""
    
    @staticmethod
    def compare_keywords_stats(keywords_data: Dict[str, Dict[str, Any]]) -> pd.DataFrame:
        """
        複数のキーワードの統計情報を計算して比較可能なDataFrameを作成
        
        Args:
            keywords_data: キーワードとそれに対応するデータの辞書
        
        Returns:
            pd.DataFrame: キーワードごとの統計情報
        """
        stats_df = pd.DataFrame()
        
        for keyword, data in keywords_data.items():
            df = data.get('df')
            if df is not None and len(df) > 0:
                stats = {
                    'キーワード': keyword,
                    '動画数': len(df),
                    '平均再生数': df['view_count'].mean() if 'view_count' in df.columns else 0,
                    '最大再生数': df['view_count'].max() if 'view_count' in df.columns else 0,
                    '中央値再生数': df['view_count'].median() if 'view_count' in df.columns else 0,
                    '平均高評価数': df['like_count'].mean() if 'like_count' in df.columns else 0,
                    '平均コメント数': df['comment_count'].mean() if 'comment_count' in df.columns else 0,
                    '平均上振れ係数': df['engagement_ratio'].mean() if 'engagement_ratio' in df.columns else 0,
                }
                
                # 安全に動画長データを取得
                if 'duration_seconds' in df.columns:
                    stats['平均動画長(秒)'] = df['duration_seconds'].mean()
                
                # コメント率の計算
                if all(col in df.columns for col in ['comment_count', 'view_count']):
                    df_valid = df[(df['view_count'] > 0) & (df['comment_count'] >= 0)]
                    if len(df_valid) > 0:
                        stats['平均コメント率'] = (df_valid['comment_count'] / df_valid['view_count']).mean()
                    else:
                        stats['平均コメント率'] = 0
                
                # 高評価率の計算
                if all(col in df.columns for col in ['like_count', 'view_count']):
                    df_valid = df[(df['view_count'] > 0) & (df['like_count'] >= 0)]
                    if len(df_valid) > 0:
                        stats['平均高評価率'] = (df_valid['like_count'] / df_valid['view_count']).mean()
                    else:
                        stats['平均高評価率'] = 0
                
                stats_df = pd.concat([stats_df, pd.DataFrame([stats])], ignore_index=True)
        
        return stats_df
    
    @staticmethod
    def create_comparison_charts(stats_df: pd.DataFrame, metric: str) -> go.Figure:
        """
        キーワード比較用のグラフを作成
        
        Args:
            stats_df: キーワードごとの統計情報
            metric: 比較する指標
        
        Returns:
            go.Figure: Plotlyグラフオブジェクト
        """
        if metric not in stats_df.columns:
            return None
        
        # ソートして棒グラフを作成
        chart_df = stats_df.sort_values(by=metric, ascending=False)
        fig = px.bar(
            chart_df,
            x='キーワード',
            y=metric,
            title=f"キーワード別 {metric}の比較",
            color='キーワード',
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        
        fig.update_layout(
            xaxis_title="キーワード",
            yaxis_title=metric,
            legend_title_text="キーワード"
        )
        
        return fig
    
    @staticmethod
    def format_stats_df(stats_df: pd.DataFrame) -> pd.DataFrame:
        """
        統計情報をフォーマットして表示用に整形
        
        Args:
            stats_df: キーワードごとの統計情報
        
        Returns:
            pd.DataFrame: フォーマット済みの統計情報
        """
        formatted_df = stats_df.copy()
        
        # 数値フォーマット
        format_mapping = {
            '平均再生数': '{:,.0f}',
            '最大再生数': '{:,.0f}',
            '中央値再生数': '{:,.0f}',
            '平均高評価数': '{:,.0f}',
            '平均コメント数': '{:,.0f}',
            '平均上振れ係数': '{:.2f}',
            '平均コメント率': '{:.2%}',
            '平均高評価率': '{:.2%}',
            '平均動画長(秒)': lambda x: f"{int(x)} 秒 ({int(x//60)}:{int(x%60):02d})"
        }
        
        for col, fmt in format_mapping.items():
            if col in formatted_df.columns:
                if callable(fmt):
                    formatted_df[col] = formatted_df[col].apply(fmt)
                else:
                    formatted_df[col] = formatted_df[col].apply(lambda x: fmt.format(x))
        
        return formatted_df
