import os
import googleapiclient.discovery
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
from datetime import datetime
import time
import json
import logging
import re
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 環境変数はmain.pyから渡されるAPIキーを使用するため、ここではload_envは不要
# load_dotenv()

class YouTubeDataAPI:
    @staticmethod
    def _parse_duration(duration_str: str) -> int:
        """Convert ISO 8601 duration (e.g., 'PT1M20S') to seconds."""
        if not duration_str:
            return 0
        pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
        match = re.match(pattern, duration_str)
        if not match:
            return 0
        hours, minutes, seconds = match.groups()
        total = (int(hours) if hours else 0) * 3600 + (int(minutes) if minutes else 0) * 60 + (int(seconds) if seconds else 0)
        return total
    def __init__(self, api_key: str):
        """
        Initialize the YouTube Data API client
        
        Args:
            api_key: YouTube API Key (required)
        """
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("YouTube API key is missing. Please provide a valid API key.")
        
        self.youtube = googleapiclient.discovery.build(
            'youtube', 'v3', developerKey=self.api_key,
            cache_discovery=False
        )
        
        # Cache to minimize API calls
        self.video_cache = {}
        self.channel_cache = {}

    def search_videos(self, query: str, max_results: int = 50, published_after: Optional[str] = None, published_before: Optional[str] = None) -> List[str]:
        """
        Search for YouTube videos based on a query and date filters
        
        Args:
            query: Search term
            max_results: Maximum number of results (default: 50)
            published_after: Filter for videos published after this date (RFC 3339 format, e.g., 2023-01-01T00:00:00Z)
            published_before: Filter for videos published before this date (RFC 3339 format, e.g., 2023-01-31T23:59:59Z)
            
        Returns:
            List of video IDs
        """
        try:
            search_params = {
                'q': query,
                'part': 'id',
                'maxResults': min(max_results, 50),  # YouTube API limit is 50
                'type': 'video',
                'relevanceLanguage': 'ja',  # Assuming Japanese content is preferred
                'order': 'viewCount'  # Sort by view count to get popular videos
            }
            
            # Add date filters if provided
            if published_after:
                search_params['publishedAfter'] = published_after
            if published_before:
                search_params['publishedBefore'] = published_before
                
            search_response = self.youtube.search().list(**search_params).execute()
            
            video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
            logger.info(f"Found {len(video_ids)} videos for query: {query}")
            return video_ids
            
        except HttpError as e:
            logger.error(f"Error searching videos: {e}")
            return []
    
    def get_videos_details(self, video_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get detailed information about videos
        
        Args:
            video_ids: List of YouTube video IDs
            
        Returns:
            List of video details
        """
        if not video_ids:
            return []
            
        videos_data = []
        # Process in batches of 50 (YouTube API limit)
        for i in range(0, len(video_ids), 50):
            batch_ids = video_ids[i:i+50]
            uncached_ids = [vid for vid in batch_ids if vid not in self.video_cache]
            
            if uncached_ids:
                try:
                    videos_response = self.youtube.videos().list(
                        id=','.join(uncached_ids),
                        part='snippet,statistics,contentDetails'
                    ).execute()
                    
                    # Update cache with new data
                    for item in videos_response.get('items', []):
                        video_id = item['id']
                        self.video_cache[video_id] = item
                        
                except HttpError as e:
                    logger.error(f"Error getting video details: {e}")
                    # Add small delay to avoid API rate limiting
                    time.sleep(1)
            
            # Add all videos (cached + newly fetched) to the result
            for video_id in batch_ids:
                if video_id in self.video_cache:
                    videos_data.append(self.video_cache[video_id])
            
            # Small pause between batches
            if i + 50 < len(video_ids):
                time.sleep(0.5)
                
        return videos_data
    
    def get_channel_details(self, channel_ids: List[str]) -> Dict[str, Any]:
        """
        Get channel details including subscriber counts
        
        Args:
            channel_ids: List of YouTube channel IDs
            
        Returns:
            Dictionary mapping channel IDs to their details
        """
        if not channel_ids:
            return {}
            
        # Remove duplicates
        unique_channel_ids = list(set(channel_ids))
        
        # Filter out already cached channels
        uncached_channels = [cid for cid in unique_channel_ids if cid not in self.channel_cache]
        
        # Get channel details in batches of 50
        for i in range(0, len(uncached_channels), 50):
            batch_ids = uncached_channels[i:i+50]
            
            if not batch_ids:
                continue
                
            try:
                channel_response = self.youtube.channels().list(
                    id=','.join(batch_ids),
                    part='snippet,statistics'
                ).execute()
                
                # Update cache
                for item in channel_response.get('items', []):
                    channel_id = item['id']
                    self.channel_cache[channel_id] = item
                    
            except HttpError as e:
                logger.error(f"Error getting channel details: {e}")
                
            # Add small delay between batches
            if i + 50 < len(uncached_channels):
                time.sleep(0.5)
                
        # Return all requested channels (from cache)
        return {cid: self.channel_cache.get(cid) for cid in unique_channel_ids if cid in self.channel_cache}
    
    def get_latest_videos_for_channel(self, channel_id: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        指定したチャンネルの最新動画を取得
        
        Args:
            channel_id: YouTubeチャンネルID
            max_results: 取得する最大動画数（デフォルト5件）
            
        Returns:
            動画データのリスト
        """
        try:
            # チャンネルの動画を検索（投稿日の降順）
            search_response = self.youtube.search().list(
                channelId=channel_id,
                part='id',
                order='date',  # 日付順（最新順）
                maxResults=max_results,
                type='video'
            ).execute()
            
            # 動画IDを抽出
            video_ids = [item['id']['videoId'] for item in search_response.get('items', []) 
                        if item.get('id', {}).get('videoId')]
            
            if not video_ids:
                return []
                
            # 動画の詳細情報を取得
            videos_data = self.get_videos_details(video_ids)
            
            return videos_data
            
        except HttpError as e:
            logger.error(f"チャンネル最新動画の取得に失敗: {e}")
            return []
    
    def format_video_data(self, videos: List[Dict[str, Any]], 
                          channels_data: Dict[str, Dict[str, Any]],
                          previous_stats: Dict[str, Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Format video data for display and export
        
        Args:
            videos: List of video data from YouTube API
            channels_data: Dictionary of channel data
            previous_stats: Previous video statistics for comparison
            
        Returns:
            List of formatted video data
        """
        formatted_data = []
        
        for video in videos:
            video_id = video['id']
            snippet = video.get('snippet', {})
            content_details = video.get('contentDetails', {})
            statistics = video.get('statistics', {})
            channel_id = snippet.get('channelId')
            
            # Get channel data
            channel_info = channels_data.get(channel_id, {})
            channel_stats = channel_info.get('statistics', {})
            
            # Calculate metrics
            view_count = int(statistics.get('viewCount', 0))
            subscriber_count = int(channel_stats.get('subscriberCount', 1))  # Avoid division by zero
            engagement_ratio = round(view_count / subscriber_count, 2) if subscriber_count > 0 else 0
            
            # 動画長（秒単位）を計算
            duration_seconds = self._parse_duration(content_details.get('duration', ''))
            
            # Calculate 24-hour view estimate if previous data exists
            estimated_24h_views = 0
            view_change = 0
            if previous_stats and video_id in previous_stats:
                prev_views = int(previous_stats[video_id].get('viewCount', 0))
                view_change = view_count - prev_views
                # Only show positive changes to avoid confusion
                estimated_24h_views = max(0, view_change)
            
            # Format publish date
            published_at = snippet.get('publishedAt', '')
            if published_at:
                try:
                    publish_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                    published_at = publish_date.strftime('%Y-%m-%d')
                except (ValueError, TypeError):
                    pass
            
            # Extract tags (limited to first 5)
            tags = snippet.get('tags', [])
            tags_str = ', '.join(tags[:5]) + ('...' if len(tags) > 5 else '') if tags else ''
            
            # Format description (first 100 chars)
            description = snippet.get('description', '')
            short_description = description[:100] + '...' if len(description) > 100 else description
            
            # Extract thumbnail URLs
            thumbnails = snippet.get('thumbnails', {})
            thumbnail_url = ''
            # Try to get highest quality thumbnail available
            for quality in ['maxres', 'high', 'medium', 'default', 'standard']:
                if quality in thumbnails and 'url' in thumbnails[quality]:
                    thumbnail_url = thumbnails[quality]['url']
                    break
            
            formatted_video = {
                'video_id': video_id,
                'title': snippet.get('title', ''),
                'channel_name': snippet.get('channelTitle', ''),
                'channel_id': channel_id,
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'published_at': published_at,
                'view_count': view_count,
                'like_count': int(statistics.get('likeCount', 0)),
                'comment_count': int(statistics.get('commentCount', 0)),
                'description': short_description,
                'tags': tags_str,
                'subscriber_count': subscriber_count,
                'engagement_ratio': engagement_ratio,
                'duration_seconds': duration_seconds,  # 動画長（秒）を追加
                'video_type': 'short' if duration_seconds < 90 else 'long',
                'estimated_24h_views': estimated_24h_views,
                'view_change': view_change,
                'thumbnail_url': thumbnail_url,  # サムネイルURLを追加
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            formatted_data.append(formatted_video)
            
        return formatted_data
