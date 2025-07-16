import os
import json
from google.oauth2.service_account import Credentials  # For service account authentication
from googleapiclient.discovery import build  # To create a Drive API service instance
from googleapiclient.http import MediaFileUpload  # To upload files
from datetime import datetime, timedelta  # For handling date operations

# Main class for uploading files to a specific folder in Google Drive
class SavingOnDriveFashionAndFamily:
    def __init__(self, credentials_dict):
        self.credentials_dict = credentials_dict  # Dictionary containing the service account credentials
        self.scopes = ['https://www.googleapis.com/auth/drive']  # Required scopes for accessing Google Drive
        self.service = None  # Will hold the authenticated Drive service object
        self.parent_folder_id = '1gNv7Dnak050_q4pXNSq2bPKtAbIQ9MOp'  # ID of the parent folder in Google Drive

    def authenticate(self):
        """Authenticate with Google Drive API."""
        try:
            print("Authenticating with Google Drive...")
            # Build credentials object from the service account info
            creds = Credentials.from_service_account_info(self.credentials_dict, scopes=self.scopes)
            # Build the Drive service object
            self.service = build('drive', 'v3', credentials=creds)
            print("Authentication successful.")
        except Exception as e:
            print(f"Authentication error: {e}")
            raise  # Re-raise the exception to be handled by the caller

    def get_folder_id(self, folder_name):
        """Get folder ID by name within the parent folder."""
        try:
            # Query to find folder with specific name under parent folder
            query = (f"name='{folder_name}' and "
                     f"'{self.parent_folder_id}' in parents and "
                     f"mimeType='application/vnd.google-apps.folder' and "
                     f"trashed=false")
            
            # Execute query using Drive API
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'  # Only retrieve file ID and name
            ).execute()
            
            files = results.get('files', [])
            if files:
                print(f"Folder '{folder_name}' found with ID: {files[0]['id']}")
                return files[0]['id']  # Return folder ID if found
            else:
                print(f"Folder '{folder_name}' does not exist.")
                return None  # Folder not found
        except Exception as e:
            print(f"Error getting folder ID: {e}")
            return None  # Return None on failure

    def create_folder(self, folder_name):
        """Create a new folder in the parent folder."""
        try:
            print(f"Creating folder '{folder_name}'...")
            # Metadata for new folder
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [self.parent_folder_id]  # Set parent folder
            }
            # Use Drive API to create the folder
            folder = self.service.files().create(
                body=file_metadata,
                fields='id'  # Only retrieve new folder ID
            ).execute()
            print(f"Folder '{folder_name}' created with ID: {folder.get('id')}")
            return folder.get('id')
        except Exception as e:
            print(f"Error creating folder: {e}")
            raise  # Re-raise error to caller

    def upload_file(self, file_name, folder_id):
        """Upload a single file to Google Drive."""
        try:
            print(f"Uploading file: {file_name}")
            # Metadata for the file to be uploaded
            file_metadata = {
                'name': os.path.basename(file_name),  # File name only (no path)
                'parents': [folder_id]  # Upload to the specified folder
            }
            # Prepare file upload body
            media = MediaFileUpload(file_name, resumable=True)
            # Create file in Drive
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'  # Only retrieve file ID
            ).execute()
            print(f"File '{file_name}' uploaded with ID: {file.get('id')}")
            return file.get('id')  # Return uploaded file ID
        except Exception as e:
            print(f"Error uploading file: {e}")
            raise  # Re-raise error to caller

    def save_files(self, files):
        """Save files to Google Drive in a folder named after yesterday's date."""
        try:
            # Calculate yesterday’s date in YYYY-MM-DD format
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            # Try to get folder ID for yesterday's folder
            folder_id = self.get_folder_id(yesterday)
            # If not found, create it
            if not folder_id:
                folder_id = self.create_folder(yesterday)
            
            # Upload all files to the folder
            for file_name in files:
                self.upload_file(file_name, folder_id)
            
            print(f"All files uploaded successfully to Google Drive folder '{yesterday}'.")
        except Exception as e:
            print(f"Error saving files: {e}")
            raise  # Re-raise for caller to handle
