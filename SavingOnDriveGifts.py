import os
import json
from google.oauth2.service_account import Credentials  # For authenticating using service account credentials
from googleapiclient.discovery import build  # Used to build the Google Drive API client
from googleapiclient.http import MediaFileUpload  # Handles file uploads to Drive
from datetime import datetime, timedelta  # For handling time and dates

class SavingOnDriveGifts:
    def __init__(self, credentials_dict):
        self.credentials_dict = credentials_dict  # JSON dictionary for service account credentials
        self.scopes = ['https://www.googleapis.com/auth/drive']  # Scope for full Drive access
        self.service = None  # Will hold the authenticated Drive service object
        self.parent_folder_id = '1IYdBh7-Rdd1aWSH8p_2Go8LkFk84xkLB'  # The ID of the parent folder where subfolders will be created

    def authenticate(self):
        """Authenticate with Google Drive API."""
        try:
            print("Authenticating with Google Drive...")
            # Create credentials from the provided dictionary
            creds = Credentials.from_service_account_info(self.credentials_dict, scopes=self.scopes)
            # Build the Drive API client with the credentials
            self.service = build('drive', 'v3', credentials=creds)
            print("Authentication successful.")
        except Exception as e:
            print(f"Authentication error: {e}")
            raise  # Re-raise exception if authentication fails

    def get_folder_id(self, folder_name):
        """Get folder ID by name within the parent folder."""
        try:
            # Query to search for a folder with the specified name under the parent folder
            query = (f"name='{folder_name}' and "
                     f"'{self.parent_folder_id}' in parents and "
                     f"mimeType='application/vnd.google-apps.folder' and "
                     f"trashed=false")
            
            # Execute the search query
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'  # We only need ID and name fields
            ).execute()
            
            files = results.get('files', [])
            if files:
                # Folder found, return its ID
                print(f"Folder '{folder_name}' found with ID: {files[0]['id']}")
                return files[0]['id']
            else:
                # Folder not found
                print(f"Folder '{folder_name}' does not exist.")
                return None
        except Exception as e:
            print(f"Error getting folder ID: {e}")
            return None  # Return None if something went wrong

    def create_folder(self, folder_name):
        """Create a new folder in the parent folder."""
        try:
            print(f"Creating folder '{folder_name}'...")
            # Define the metadata for the new folder
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [self.parent_folder_id]  # Set the parent folder
            }
            # Use the Drive API to create the folder
            folder = self.service.files().create(
                body=file_metadata,
                fields='id'  # Return the new folder's ID
            ).execute()
            print(f"Folder '{folder_name}' created with ID: {folder.get('id')}")
            return folder.get('id')
        except Exception as e:
            print(f"Error creating folder: {e}")
            raise  # Raise the exception to the caller

    def upload_file(self, file_name, folder_id):
        """Upload a single file to Google Drive."""
        try:
            print(f"Uploading file: {file_name}")
            # Metadata for the uploaded file, including its target folder
            file_metadata = {
                'name': os.path.basename(file_name),  # Use only the file name, not full path
                'parents': [folder_id]  # Upload into the specified folder
            }
            # Prepare the file for upload
            media = MediaFileUpload(file_name, resumable=True)
            # Upload the file using Drive API
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'  # Return the file ID
            ).execute()
            print(f"File '{file_name}' uploaded with ID: {file.get('id')}")
            return file.get('id')
        except Exception as e:
            print(f"Error uploading file: {e}")
            raise  # Raise the error to be handled externally

    def save_files(self, files):
        """Save files to Google Drive in a folder named after yesterday's date."""
        try:
            # Get yesterday’s date as a string (e.g., '2025-07-15')
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

            # Try to get the folder ID for the date folder
            folder_id = self.get_folder_id(yesterday)
            # If folder doesn't exist, create it
            if not folder_id:
                folder_id = self.create_folder(yesterday)
            
            # Upload each file to the folder
            for file_name in files:
                self.upload_file(file_name, folder_id)
            
            print(f"All files uploaded successfully to Google Drive folder '{yesterday}'.")
        except Exception as e:
            print(f"Error saving files: {e}")
            raise  # Let the caller handle the exception

