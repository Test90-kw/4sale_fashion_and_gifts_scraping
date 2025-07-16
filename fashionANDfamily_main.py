import asyncio
import pandas as pd
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from pathlib import Path
from DetailsScraper import DetailsScraping  # Your scraping logic
from SavingOnDriveFashionAndFamily import SavingOnDriveFashionAndFamily  # Your Drive upload logic


class FashionAndFamilyMainScraper:
    def __init__(self, fashionANDfamilys_data: Dict[str, List[Tuple[str, int]]]):
        self.fashionANDfamilys_data = fashionANDfamilys_data  # Dictionary with category name and URL/page count tuples
        self.chunk_size = 2  # How many categories to process per chunk
        self.max_concurrent_links = 2  # Max pages to scrape concurrently
        self.logger = logging.getLogger(__name__)
        self.setup_logging()  # Initialize logging
        self.temp_dir = Path("temp_files")  # Folder to temporarily store Excel files
        self.temp_dir.mkdir(exist_ok=True)
        self.upload_retries = 3  # Max attempts to retry uploads
        self.upload_retry_delay = 15  # Delay (seconds) between upload retries
        self.page_delay = 3  # Delay between scraping each page
        self.chunk_delay = 10  # Delay between scraping each chunk

    def setup_logging(self):
        """Initialize logging configuration."""
        stream_handler = logging.StreamHandler()  # Log to console
        file_handler = logging.FileHandler("scraper.log")  # Log to file

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[stream_handler, file_handler],
        )
        self.logger.setLevel(logging.INFO)
        print("Logging setup complete.")

    async def scrape_fashionANDfamily(self, fashionANDfamily_name: str, urls: List[Tuple[str, int]], semaphore: asyncio.Semaphore) -> List[Dict]:
        """Scrape data for a single category."""
        self.logger.info(f"Starting to scrape {fashionANDfamily_name}")
        card_data = []
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")  # Only include listings from yesterday

        async with semaphore:  # Limit concurrency
            for url_template, page_count in urls:
                for page in range(1, page_count + 1):
                    url = url_template.format(page)
                    scraper = DetailsScraping(url)
                    try:
                        cards = await scraper.get_card_details()
                        for card in cards:
                            if card.get("date_published") and card.get("date_published", "").split()[0] == yesterday:
                                card_data.append(card)

                        await asyncio.sleep(self.page_delay)
                    except Exception as e:
                        self.logger.error(f"Error scraping {url}: {e}")
                        continue

        return card_data

    async def save_to_excel(self, fashionANDfamily_name: str, card_data: List[Dict]) -> str:
        """Save scraped data to an Excel file."""
        if not card_data:
            self.logger.info(f"No data to save for {fashionANDfamily_name}, skipping Excel file creation.")
            return None

        safe_name = fashionANDfamily_name.replace('/', '_').replace('\\', '_')  # Sanitize file name
        excel_file = Path(f"{safe_name}.xlsx")
        try:
            df = pd.DataFrame(card_data)
            df.to_excel(excel_file, index=False)
            self.logger.info(f"Successfully saved data for {fashionANDfamily_name}")
            return str(excel_file)
        except Exception as e:
            self.logger.error(f"Error saving Excel file {excel_file}: {e}")
            return None

    async def upload_files_with_retry(self, drive_saver, files: List[str]) -> List[str]:
        """Upload files to Google Drive with retry mechanism."""
        uploaded_files = []
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        try:
            self.logger.info(f"Checking local files before upload: {files}")
            for file in files:
                self.logger.info(f"File {file} exists: {os.path.exists(file)}, size: {os.path.getsize(file) if os.path.exists(file) else 'N/A'}")

            folder_id = drive_saver.get_folder_id(yesterday)
            if not folder_id:
                self.logger.info(f"Creating new folder for date: {yesterday}")
                folder_id = drive_saver.create_folder(yesterday)

            for file in files:
                for attempt in range(self.upload_retries):
                    try:
                        if os.path.exists(file):
                            file_id = drive_saver.upload_file(file, folder_id)
                            if not file_id:
                                raise Exception("Upload returned no file ID")
                            uploaded_files.append(file)
                            self.logger.info(f"Successfully uploaded {file} with ID: {file_id}")
                            break
                        else:
                            self.logger.error(f"File not found for upload: {file}")
                            break
                    except Exception as e:
                        self.logger.error(f"Upload attempt {attempt + 1} failed for {file}: {e}")
                        if attempt < self.upload_retries - 1:
                            self.logger.info(f"Retrying after {self.upload_retry_delay} seconds...")
                            await asyncio.sleep(self.upload_retry_delay)
                            drive_saver.authenticate()
                        else:
                            self.logger.error(f"Failed to upload {file} after {self.upload_retries} attempts")

        except Exception as e:
            self.logger.error(f"Error in upload process: {e}")
            raise

        return uploaded_files
    
    async def scrape_all_fashionANDfamilys(self):
        """Scrape all categories and handle uploads."""
        self.temp_dir.mkdir(exist_ok=True)

        # Setup Google Drive
        try:
            credentials_json = os.environ.get("FF_GCLOUD_KEY_JSON")
            if not credentials_json:
                raise EnvironmentError("FF_GCLOUD_KEY_JSON environment variable not found")
            else:
                self.logger.info("Environment variable FF_GCLOUD_KEY_JSON is set.")

            credentials_dict = json.loads(credentials_json)
            drive_saver = SavingOnDriveFashionAndFamily(credentials_dict)
            drive_saver.authenticate()
            self.logger.info("Testing Drive API access...")
            try:
                drive_saver.service.files().get(fileId=drive_saver.parent_folder_id).execute()
                self.logger.info("Successfully accessed parent folder")
            except Exception as e:
                self.logger.error(f"Failed to access parent folder: {e}")
                return
        except Exception as e:
            self.logger.error(f"Failed to setup Google Drive: {e}")
            return

        fashionANDfamilys_chunks = [
            list(self.fashionANDfamilys_data.items())[i : i + self.chunk_size]
            for i in range(0, len(self.fashionANDfamilys_data), self.chunk_size)
        ]

        semaphore = asyncio.Semaphore(self.max_concurrent_links)

        for chunk_index, chunk in enumerate(fashionANDfamilys_chunks, 1):
            self.logger.info(f"Processing chunk {chunk_index}/{len(fashionANDfamilys_chunks)}")

            tasks = []
            for fashionANDfamily_name, urls in chunk:
                task = asyncio.create_task(self.scrape_fashionANDfamily(fashionANDfamily_name, urls, semaphore))
                tasks.append((fashionANDfamily_name, task))
                await asyncio.sleep(2)

            pending_uploads = []
            for fashionANDfamily_name, task in tasks:
                try:
                    card_data = await task
                    if card_data:
                        excel_file = await self.save_to_excel(fashionANDfamily_name, card_data)
                        if excel_file:
                            pending_uploads.append(excel_file)
                except Exception as e:
                    self.logger.error(f"Error processing {fashionANDfamily_name}: {e}")

            if pending_uploads:
                await self.upload_files_with_retry(drive_saver, pending_uploads)

                for file in pending_uploads:
                    try:
                        os.remove(file)
                        self.logger.info(f"Cleaned up local file: {file}")
                    except Exception as e:
                        self.logger.error(f"Error cleaning up {file}: {e}")

            if chunk_index < len(fashionANDfamilys_chunks):
                self.logger.info(f"Waiting {self.chunk_delay} seconds before next chunk...")
                await asyncio.sleep(self.chunk_delay)


if __name__ == "__main__":
    # Dictionary defining all categories and their paginated URLs
    fashionANDfamilys_data = {
        "صالات رياضة و منتجعات صحية": [("https://www.q84sale.com/ar/fashion-and-family/gym-and-spa/{}", 2)],
        "ملابس رجالية": [("https://www.q84sale.com/ar/fashion-and-family/men-clothes/{}", 1)],
        "أحذية رجالية": [("https://www.q84sale.com/ar/fashion-and-family/men-shoes/{}", 1)],
        "منتجات العناية بالرجال": [("https://www.q84sale.com/ar/fashion-and-family/men-care-products/{}", 1)],
        "ملابس نسائية": [("https://www.q84sale.com/ar/fashion-and-family/ladies-clothes/{}", 1)],
        "شنط و احذية نسائية": [("https://www.q84sale.com/ar/fashion-and-family/women-bags-and-shoes/{}", 1)],
        "مستحضرات تجميل نسائية": [("https://www.q84sale.com/ar/fashion-and-family/women-makeup-and-care-products/{}", 1)],
        "اكسسورات نسائية": [("https://www.q84sale.com/ar/fashion-and-family/women-accessories/{}", 1)],
        "ملابس أطفال": [("https://www.q84sale.com/ar/fashion-and-family/baby-clothes/{}", 1)],
        "لعب أطفال": [("https://www.q84sale.com/ar/fashion-and-family/children-toys/{}", 1)],
        "مستلزمات أطفال": [("https://www.q84sale.com/ar/fashion-and-family/baby-products/{}", 1)],
        "لوازم الأسرة": [("https://www.q84sale.com/ar/fashion-and-family/family-supplies/{}", 1)],
    }


    
    async def main():
        scraper = FashionAndFamilyMainScraper(fashionANDfamilys_data)
        await scraper.scrape_all_fashionANDfamilys()
        

    asyncio.run(main())
