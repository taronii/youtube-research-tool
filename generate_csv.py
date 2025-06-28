import os
import pandas as pd
import argparse
from datetime import datetime
from dotenv import load_dotenv
import logging
from typing import List, Dict, Any

# Local imports
from get_video_data import YouTubeDataAPI
from update_gsheet import GoogleSheetsManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def generate_csv(search_query: str = None, max_results: int = 50, output_path: str = None):
    """
    Generate CSV with YouTube video data based on search query
    
    Args:
        search_query: YouTube search query
        max_results: Maximum number of results to fetch
        output_path: Path to save the CSV file
    """
    try:
        # Use default query if none provided
        if not search_query:
            search_query = os.getenv('DEFAULT_SEARCH_QUERY', 'プログラミング')
        
        # Default max results
        if not max_results:
            max_results = int(os.getenv('MAX_RESULTS', '50'))
            
        # Default output path
        if not output_path:
            today = datetime.now().strftime('%Y%m%d')
            output_path = f'youtube_data_{today}.csv'
            
        logger.info(f"Starting CSV generation for query: {search_query}")
        
        # Initialize YouTube API client
        youtube_client = YouTubeDataAPI()
        
        # Initialize Google Sheets manager to get historical data
        sheets_manager = GoogleSheetsManager()
        
        # Get previous video statistics
        previous_stats = sheets_manager.get_previous_stats()
        
        # Search for videos
        video_ids = youtube_client.search_videos(search_query, max_results)
        
        if not video_ids:
            logger.warning("No videos found for the query.")
            return
            
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
        
        # Create DataFrame and save to CSV
        df = pd.DataFrame(formatted_data)
        
        # dfが存在し、データがあるか確認
        if df is not None and not df.empty:
            df.to_csv(output_path, index=False, encoding='utf-8-sig')  # utf-8-sig for Excel compatibility
        else:
            logger.warning("No data to save to CSV")
            return False
        
        logger.info(f"CSV file saved to: {output_path}")
        
        # Update Google Sheets with the new data
        sheets_manager.update_video_history(formatted_data)
        sheets_manager.update_current_data(formatted_data)
        
        logger.info("Google Sheets updated successfully")
        
        return output_path
        
    except Exception as e:
        logger.error(f"Error generating CSV: {e}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate CSV with YouTube video data")
    parser.add_argument("--query", type=str, help="YouTube search query")
    parser.add_argument("--max-results", type=int, default=50, help="Maximum number of results")
    parser.add_argument("--output", type=str, help="Output CSV file path")
    
    args = parser.parse_args()
    
    generate_csv(
        search_query=args.query,
        max_results=args.max_results,
        output_path=args.output
    )
