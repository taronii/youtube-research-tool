import re
import logging
import pandas as pd
from collections import Counter
from typing import List, Dict, Tuple, Any
import matplotlib.pyplot as plt
import japanize_matplotlib
import seaborn as sns

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TagAnalyzer:
    """
    YouTube動画のタグやキーワードを分析するためのクラス
    """
    def __init__(self):
        """初期化"""
        # 除外する一般的な単語（ストップワード）
        self.stopwords = {
            'について', 'とは', 'する', 'ある', 'いる', 'なる', 'れる', 'この', 'その',
            'あの', 'どの', 'これ', 'それ', 'あれ', 'どれ', 'こと', 'もの', 'ため',
            'ところ', 'よう', 'こちら', 'そちら', 'あちら', 'どちら', 'さん', 'くん',
            'ちゃん', 'さま', '様', 'で', 'を', 'の', 'が', 'に', 'と', 'へ', 'から',
            'まで', 'より', 'や', 'これ', 'それ', 'あれ', 'この', 'その', 'あの', '私',
            '僕', '俺', '君', 'です', 'ます', '#', '@', '!', '！', '?', '？', '…', '・',
            '...', '「', '」', '【', '】', '（', '）', '(', ')', '〜', ':', '：', ';',
            '；', ',', '、', '.', '。', '/', '／', '〈', '〉', '《', '》', '=', '＝',
            '+', '＋', '-', 'ー', '*', '＊', 'x', 'X', '×', '|', '｜', '日', '月', '年',
            '月', '週', '時間', '分', '秒', '時', '今回', '前回', 'こちら', 'そちら',
            '方法', 'どんな', 'みたい', 'たい', 'てる', 'です', 'ます'
        }
    
    def analyze_tags(self, videos_data: List[Dict[str, Any]]) -> Tuple[List[Tuple[str, int]], pd.DataFrame]:
        """
        動画タグを分析して頻度順にランキング

        Args:
            videos_data: 動画データのリスト

        Returns:
            タグの頻度ランキングとタグの出現頻度データフレーム
        """
        # タグのカウント
        tag_counter = Counter()
        
        # 各動画から全てのタグを収集
        for video in videos_data:
            # tags フィールドがリストの場合だけ処理
            tags = video.get('tags', [])
            if isinstance(tags, list):
                for tag in tags:
                    if tag and len(tag) >= 2:  # 最低2文字以上のタグを対象
                        tag_counter[tag.lower()] += 1
        
        # 頻度順にソート
        top_tags = tag_counter.most_common(30)  # 上位30件まで
        
        # データフレームに変換（可視化用）
        df_tags = pd.DataFrame(top_tags, columns=['tag', 'count'])
        
        return top_tags, df_tags
    
    def extract_keywords(self, videos_data: List[Dict[str, Any]], 
                         fields: List[str] = ['title', 'description']) -> Tuple[List[Tuple[str, int]], pd.DataFrame]:
        """
        動画タイトルと説明文から重要キーワードを抽出

        Args:
            videos_data: 動画データのリスト
            fields: 抽出対象のフィールド（デフォルトはタイトルと説明文）

        Returns:
            キーワードの頻度ランキングとキーワードの出現頻度データフレーム
        """
        # 全てのテキストを結合
        all_text = []
        for video in videos_data:
            for field in fields:
                text = video.get(field, '')
                if text and isinstance(text, str):
                    all_text.append(text)
        
        # テキストを単語に分割（簡易的な分割）
        words = []
        for text in all_text:
            # 記号などを削除してスペースで分割
            cleaned_text = re.sub(r'[【】「」『』（）［］{}\[\]()!！?？…・.。,:：;；\s]+', ' ', text)
            words.extend(cleaned_text.split())
        
        # ストップワードを削除し、頻度カウント
        word_counter = Counter()
        for word in words:
            if len(word) >= 2 and word.lower() not in self.stopwords:
                word_counter[word] += 1
        
        # 頻度順にソート
        top_keywords = word_counter.most_common(30)  # 上位30件まで
        
        # データフレームに変換（可視化用）
        df_keywords = pd.DataFrame(top_keywords, columns=['keyword', 'count'])
        
        return top_keywords, df_keywords
    
    def create_tag_chart(self, df_tags: pd.DataFrame, title: str = "人気タグランキング", limit: int = 15) -> plt.Figure:
        """
        タグの棒グラフを作成

        Args:
            df_tags: タグの頻度データフレーム
            title: グラフのタイトル
            limit: 表示するタグの数

        Returns:
            matplotlib図オブジェクト
        """
        if df_tags.empty or len(df_tags) == 0:
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.text(0.5, 0.5, "タグデータがありません", ha='center', va='center', fontsize=14)
            ax.axis('off')
            return fig
            
        # 上位のみ表示
        df_display = df_tags.head(limit)
        
        # グラフ作成
        fig, ax = plt.subplots(figsize=(10, max(6, len(df_display) * 0.4)))
        
        # 横向きの棒グラフ
        bars = ax.barh(df_display['tag'], df_display['count'], color=sns.color_palette("viridis", len(df_display)))
        
        # ラベルと値を表示
        for bar in bars:
            width = bar.get_width()
            ax.text(width + 0.3, bar.get_y() + bar.get_height()/2, f"{width:.0f}", 
                    ha='left', va='center')
        
        # グラフの設定
        ax.set_title(title, fontsize=16)
        ax.set_xlabel('出現回数', fontsize=12)
        ax.set_ylabel('タグ', fontsize=12)
        
        # Y軸を反転（上位を上に表示）
        ax.invert_yaxis()
        
        plt.tight_layout()
        return fig
    
    def create_keyword_chart(self, df_keywords: pd.DataFrame, title: str = "人気キーワードランキング", 
                           limit: int = 15) -> plt.Figure:
        """
        キーワードの棒グラフを作成

        Args:
            df_keywords: キーワードの頻度データフレーム
            title: グラフのタイトル
            limit: 表示するキーワードの数

        Returns:
            matplotlib図オブジェクト
        """
        return self.create_tag_chart(df_keywords, title, limit)

# 単体テスト用
if __name__ == "__main__":
    # テスト用データ
    test_data = [
        {
            'title': 'これが本当の筋トレ方法だ！初心者必見のコツとフォーム',
            'description': '筋トレ初心者向けの解説動画です。正しいフォームとコツを紹介します。',
            'tags': ['筋トレ', '初心者', 'トレーニング', 'ダイエット', 'フィットネス']
        },
        {
            'title': '最速で痩せる！効果的なダイエット方法',
            'description': '効率的に痩せるための方法を紹介します。食事管理と筋トレの組み合わせが重要です。',
            'tags': ['ダイエット', '痩せる', '食事管理', '筋トレ', '健康']
        },
        {
            'title': '【筋トレ】腹筋を6パックにする方法',
            'description': '腹筋を割るためのトレーニング方法と食事のアドバイスをします。',
            'tags': ['筋トレ', '腹筋', '6パック', 'トレーニング', 'ダイエット']
        }
    ]
    
    analyzer = TagAnalyzer()
    top_tags, df_tags = analyzer.analyze_tags(test_data)
    top_keywords, df_keywords = analyzer.extract_keywords(test_data)
    
    print("人気タグ:")
    for tag, count in top_tags:
        print(f"{tag}: {count}")
    
    print("\n人気キーワード:")
    for word, count in top_keywords:
        print(f"{word}: {count}")
    
    # グラフ作成テスト
    fig_tags = analyzer.create_tag_chart(df_tags)
    plt.savefig('test_tags.png')
    
    fig_keywords = analyzer.create_keyword_chart(df_keywords)
    plt.savefig('test_keywords.png')
