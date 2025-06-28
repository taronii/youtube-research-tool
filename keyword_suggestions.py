import os
import json
import requests
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
from urllib.parse import quote_plus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KeywordSuggestionManager:
    """
    YouTube関連キーワードサジェスト機能を提供するクラス
    キャッシュを活用して効率的にサジェスト検索を行う
    """
    def __init__(self, cache_dir: str = ".cache"):
        """
        初期化
        
        Args:
            cache_dir: キャッシュファイルを保存するディレクトリパス
        """
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(cache_dir, "keyword_suggestions_cache.json")
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_expiry_hours = 24  # キャッシュの有効期間（時間）
        
        # キャッシュディレクトリがなければ作成
        os.makedirs(cache_dir, exist_ok=True)
        
        # 既存のキャッシュをロード
        self._load_cache()
    
    def _load_cache(self) -> None:
        """キャッシュファイルを読み込む"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                logger.info(f"キャッシュをロードしました: {len(self.cache)}件のキーワード")
            else:
                logger.info("キャッシュファイルが見つかりません。新規作成します。")
                self.cache = {}
        except Exception as e:
            logger.error(f"キャッシュ読み込みエラー: {e}")
            self.cache = {}
    
    def _save_cache(self) -> None:
        """キャッシュをファイルに保存する"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
            logger.info(f"キャッシュを保存しました: {len(self.cache)}件のキーワード")
        except Exception as e:
            logger.error(f"キャッシュ保存エラー: {e}")
    
    def _is_cache_valid(self, keyword: str) -> bool:
        """
        キーワードのキャッシュが有効かどうか判定
        
        Args:
            keyword: 検索キーワード
            
        Returns:
            キャッシュが有効な場合はTrue
        """
        if keyword not in self.cache:
            return False
        
        cache_time_str = self.cache[keyword].get('timestamp')
        if not cache_time_str:
            return False
        
        try:
            cache_time = datetime.fromisoformat(cache_time_str)
            expiry_time = datetime.now() - timedelta(hours=self.cache_expiry_hours)
            return cache_time > expiry_time
        except:
            return False
    
    def get_suggestions(self, keyword: str, max_count: int = 10) -> List[str]:
        """
        キーワードに関連するサジェストを取得
        
        Args:
            keyword: 検索キーワード
            max_count: 最大取得数
            
        Returns:
            関連キーワードのリスト
        """
        # キャッシュチェック
        if self._is_cache_valid(keyword):
            logger.info(f"キャッシュからサジェストを取得: {keyword}")
            return self.cache[keyword].get('suggestions', [])[:max_count]
        
        # キャッシュになければ取得
        suggestions = self._fetch_suggestions(keyword)
        
        # キャッシュに保存
        self.cache[keyword] = {
            'suggestions': suggestions,
            'timestamp': datetime.now().isoformat()
        }
        self._save_cache()
        
        return suggestions[:max_count]
    
    def _fetch_suggestions(self, keyword: str) -> List[str]:
        """
        YouTubeのサジェストを取得（非公式API使用）
        
        Args:
            keyword: 検索キーワード
            
        Returns:
            サジェストキーワードのリスト
        """
        suggestions = []
        try:
            # YouTubeサジェストを取得するURL
            encoded_keyword = quote_plus(keyword)
            youtube_url = f"http://suggestqueries.google.com/complete/search?client=youtube&ds=yt&q={encoded_keyword}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(youtube_url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                # レスポンスはJSONPのような形式なので、適切に処理
                text = response.text
                if text.startswith('window.google.ac.h('):
                    text = text.strip('window.google.ac.h(').rstrip(')')
                    data = json.loads(text)
                    if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
                        suggestions = [item[0] for item in data[1] if isinstance(item, list) and len(item) > 0]
                        
            logger.info(f"YouTube検索サジェスト取得: {keyword} -> {len(suggestions)}件")
            
            # 代替手段として、一般的な関連キーワードを返す
            if not suggestions:
                suggestions = self._get_fallback_suggestions(keyword)
        except Exception as e:
            logger.error(f"サジェスト取得エラー: {e}")
            suggestions = self._get_fallback_suggestions(keyword)
        
        return suggestions
    
    def _get_fallback_suggestions(self, keyword: str) -> List[str]:
        """
        APIが失敗した場合のフォールバック
        キーワードに基づいた関連ワードを返す
        
        Args:
            keyword: 検索キーワード
            
        Returns:
            関連キーワードのリスト
        """
        # 一般的な修飾語のセット
        japanese_modifiers = ["方法", "やり方", "コツ", "入門", "初心者", "上級者", "おすすめ", 
                           "ランキング", "比較", "レビュー", "解説", "講座", "チュートリアル",
                           "最新", "人気", "話題", "トレンド", "短編", "長編"]
        
        return [f"{keyword} {modifier}" for modifier in japanese_modifiers]

# 単体テスト用
if __name__ == "__main__":
    manager = KeywordSuggestionManager()
    keyword = "ダイエット"
    suggestions = manager.get_suggestions(keyword)
    print(f"「{keyword}」の関連キーワード:")
    for i, suggestion in enumerate(suggestions, 1):
        print(f"{i}. {suggestion}")
