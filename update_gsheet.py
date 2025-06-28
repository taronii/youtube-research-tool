import os
import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from datetime import datetime
import logging
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class GoogleSheetsManager:
    def __init__(self, 
                 credentials_path: Optional[str] = None, 
                 spreadsheet_id: Optional[str] = None):
        """
        Initialize Google Sheets manager
        
        Args:
            credentials_path: Path to Google service account credentials JSON or JSON string
            spreadsheet_id: Google Spreadsheet ID
        """
        # 環境変数からの値取得
        env_creds = os.getenv('GOOGLE_CREDS_JSON_PATH')
        
        # 直接指定された認証情報とフォールバック
        self.creds_path = credentials_path or env_creds
        self.spreadsheet_id = spreadsheet_id or os.getenv('GOOGLE_SHEETS_ID')
        
        # 認証情報の存在チェック
        if not self.creds_path:
            raise ValueError("Google credentials path is missing. Please set GOOGLE_CREDS_JSON_PATH environment variable.")
        if not self.spreadsheet_id:
            raise ValueError("Google spreadsheet ID is missing. Please set GOOGLE_SHEETS_ID environment variable.")
        
        # 一時ファイルのパス (JSON文字列が渡された場合に使用)
        self.temp_creds_file = None
            
        # Define the scopes
        self.scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Initialize Google Sheets client
        self.client = None
        self.spreadsheet = None
        self._authenticate()
        
    def _authenticate(self):
        """Authenticate with Google Sheets API"""
        import tempfile
        import json
        
        try:
            # 認証情報がJSON文字列かファイルパスか判定
            is_json_string = False
            
            # JSON文字列の場合（通常「{」で始まるか、'='を含む）
            if self.creds_path and (self.creds_path.startswith('{') or '=' in self.creds_path):
                try:
                    # 環境変数に'='が含まれる場合（'GSHEET_CREDENTIALS_JSON='のような接頭辞がある場合）
                    if '=' in self.creds_path:
                        # '='以降の部分を取得
                        parts = self.creds_path.split('=', 1)
                        if len(parts) > 1:
                            json_str = parts[1].strip("'\"")
                        else:
                            json_str = self.creds_path
                    else:
                        json_str = self.creds_path
                    
                    # シングルクォートで囲まれている場合は削除
                    if json_str.startswith("'") and json_str.endswith("'"):
                        json_str = json_str[1:-1]
                    
                    # ダブルクォートで囲まれている場合は削除
                    if json_str.startswith('"') and json_str.endswith('"'):
                        json_str = json_str[1:-1]
                    
                    is_json_string = True
                    logger.debug(f"Processing JSON string starting with: {json_str[:20]}...")
                    
                    # JSONの検証と一時ファイル作成
                    try:
                        # JSON文字列がクォートされた場合、一度クォートを取り除く
                        json_obj = json.loads(json_str)
                        
                        # 一時ファイル作成
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
                        json_data = json.dumps(json_obj)
                        temp_file.write(json_data.encode('utf-8'))
                        temp_file.close()
                        
                        # 一時ファイルのパスを保存
                        self.temp_creds_file = temp_file.name
                        actual_creds_path = self.temp_creds_file
                        
                        logger.info(f"Created temporary credentials file at {actual_creds_path}")
                    except json.JSONDecodeError as jde:
                        logger.error(f"Invalid JSON string in credentials: {jde}")
                        raise ValueError(f"The credentials provided are not valid JSON: {jde}")
                except Exception as e:
                    logger.error(f"Error processing credentials: {e}")
                    raise ValueError(f"Failed to process credentials: {e}")
            else:
                # 通常のファイルパスの場合
                actual_creds_path = self.creds_path
            
            # 認証処理
            credentials = Credentials.from_service_account_file(
                actual_creds_path, scopes=self.scopes
            )
            self.client = gspread.authorize(credentials)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            logger.info("Successfully authenticated with Google Sheets")
            
        except Exception as e:
            logger.error(f"Error authenticating with Google Sheets: {e}")
            # 一時ファイルの削除を試行
            if self.temp_creds_file and os.path.exists(self.temp_creds_file):
                try:
                    os.unlink(self.temp_creds_file)
                except:
                    pass
            raise
            
    def __del__(self):
        """デストラクタ - 一時ファイルのクリーンアップ"""
        if hasattr(self, 'temp_creds_file') and self.temp_creds_file and os.path.exists(self.temp_creds_file):
            try:
                os.unlink(self.temp_creds_file)
                logger.info(f"Removed temporary credentials file: {self.temp_creds_file}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary credentials file: {e}")
    
    def get_previous_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the previous video statistics from the spreadsheet
        
        Returns:
            Dictionary mapping video IDs to their statistics
        """
        try:
            # Try to open the history sheet
            try:
                history_sheet = self.spreadsheet.worksheet('video_history')
            except gspread.exceptions.WorksheetNotFound:
                # Create sheet if it doesn't exist
                logger.info("Creating video_history sheet as it doesn't exist")
                history_sheet = self.spreadsheet.add_worksheet(
                    title='video_history',
                    rows=1000, 
                    cols=20
                )
                headers = ['video_id', 'view_count', 'date']
                history_sheet.append_row(headers)
                return {}
                
            # Get all data from the sheet
            all_data = history_sheet.get_all_records()
            
            if not all_data:
                return {}
                
            # Convert to DataFrame
            df = pd.DataFrame(all_data)
            
            # 全てのdf参照前にガード条件を追加
            if df is None or df.empty:
                logger.warning("No history data available")
                return {}
                
            # Get the latest records for each video
            try:
                # 必要なカラムが存在するか確認
                if 'date' not in df.columns or 'video_id' not in df.columns:
                    logger.warning("Required columns missing in history data")
                    return {}
                    
                df['date'] = pd.to_datetime(df['date'])
                latest_records = df.sort_values('date').drop_duplicates('video_id', keep='last')
            except Exception as e:
                logger.error(f"Error processing history data: {e}")
                return {}
            
            # Convert to dictionary
            stats_dict = {}
            for _, row in latest_records.iterrows():
                stats_dict[row['video_id']] = {
                    'viewCount': row['view_count'],
                    'date': row['date']
                }
                
            logger.info(f"Loaded previous stats for {len(stats_dict)} videos")
            return stats_dict
            
        except Exception as e:
            logger.error(f"Error getting previous stats: {e}")
            return {}
        
    def update_video_history(self, videos_data: List[Dict[str, Any]]):
        """
        Update the video history in the spreadsheet
        
        Args:
            videos_data: List of formatted video data
        """
        if not videos_data:
            logger.warning("No video data to update in spreadsheet")
            return
            
        try:
            # Try to open the history sheet
            try:
                history_sheet = self.spreadsheet.worksheet('video_history')
            except gspread.exceptions.WorksheetNotFound:
                # Create sheet if it doesn't exist
                history_sheet = self.spreadsheet.add_worksheet(
                    title='video_history', 
                    rows=1000, 
                    cols=20
                )
                headers = ['video_id', 'view_count', 'date']
                history_sheet.append_row(headers)
            
            # Prepare data for update
            current_date = datetime.now().strftime('%Y-%m-%d')
            new_rows = []
            
            for video in videos_data:
                new_rows.append([
                    video['video_id'],
                    video['view_count'],
                    current_date
                ])
            
            # Append data to sheet
            if new_rows:
                history_sheet.append_rows(new_rows)
                logger.info(f"Updated history for {len(new_rows)} videos")
                
        except Exception as e:
            logger.error(f"Error updating video history: {e}")
            
    def update_current_data(self, videos_data: List[Dict[str, Any]]):
        """
        Update the current data sheet with latest video information
        
        Args:
            videos_data: List of formatted video data
        """
        if not videos_data:
            logger.warning("No video data to update in spreadsheet")
            return
            
        try:
            # Get or create the current data sheet
            try:
                current_sheet = self.spreadsheet.worksheet('current_data')
            except gspread.exceptions.WorksheetNotFound:
                current_sheet = self.spreadsheet.add_worksheet(
                    title='current_data', 
                    rows=1000, 
                    cols=20
                )
            
            # Convert to DataFrame
            df = pd.DataFrame(videos_data)
            
            # Clear the sheet and update with new data
            current_sheet.clear()
            set_with_dataframe(current_sheet, df)
            
            logger.info(f"Updated current data sheet with {len(videos_data)} videos")
            
        except Exception as e:
            logger.error(f"Error updating current data: {e}")
