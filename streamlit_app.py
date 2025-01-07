import os
import shutil
import streamlit as st
from zipfile import ZipFile
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from PIL import Image
import requests
from io import BytesIO
import threading
import time

# Function to clean up the temporary directory
def cleanup_tmp_dir():
    tmp_dir = "/tmp"
    while True:
        try:
            for file in os.listdir(tmp_dir):
                file_path = os.path.join(tmp_dir, file)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
        except Exception as e:
            print(f"Error during cleanup: {e}")
        time.sleep(600)  # Wait for 10 minutes before next cleanup

# Start the cleanup thread
cleanup_thread = threading.Thread(target=cleanup_tmp_dir, daemon=True)
cleanup_thread.start()

# Function to download an image
def download_image(url):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGB")
    except Exception as e:
        print(f"Failed to download image: {e}")
        return None

# Function to fetch images from a chapter URL
def fetch_images(chapter_url):
    try:
        response = requests.get(chapter_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find images in the 'reading-content' class
        reading_content = soup.find(class_="reading-content")
        if not reading_content:
            st.error("No images found in the chapter.")
            return []

        return [
            urljoin(chapter_url, img['src'])
            for img in reading_content.find_all('img') if 'src' in img.attrs
        ]
    except Exception as e:
        print(f"Error fetching images: {e}")
        return []

# Function to save images as a PDF
def save_images_as_pdf(images, pdf_path):
    if not images:
        st.error("No images to save as PDF.")
        return None
    try:
        images[0].save(pdf_path, save_all=True, append_images=images[1:])
        return pdf_path
    except Exception as e:
        print(f"Error saving PDF: {e}")
        return None

# Main function for the app
def main():
    st.title("Manhwa Downloader")
    st.write("Download manhwa chapters as PDFs or ZIP files.")

    # Input fields
    base_url = st.text_input("Enter the base URL (e.g., https://example.com/manga):")
    start_chapter = st.number_input("Start Chapter", min_value=1, step=1)
    end_chapter = st.number_input("End Chapter", min_value=1, step=1)

    if st.button("Download Chapters"):
        if not base_url.strip():
            st.error("Base URL is required.")
            return

        tmp_dir = "/tmp"
        os.makedirs(tmp_dir, exist_ok=True)
        zip_file_path = os.path.join(tmp_dir, "manhwa_chapters.zip")

        manga_name = base_url.rstrip('/').split('/')[-1]

        with ZipFile(zip_file_path, "w") as zipf:
            for chapter in range(int(start_chapter), int(end_chapter) + 1):
                st.write(f"Processing Chapter {chapter}...")
                chapter_url = f"{base_url}/chapter-{chapter}/"
                image_urls = fetch_images(chapter_url)

                if not image_urls:
                    st.error(f"No images found for Chapter {chapter}. Skipping.")
                    continue

                images = []
                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = [executor.submit(download_image, url) for url in image_urls]
                    for future in futures:
                        img = future.result()
                        if img:
                            images.append(img)

                if images:
                    pdf_name = f"{manga_name}-Chapter-{chapter}.pdf"
                    pdf_path = os.path.join(tmp_dir, pdf_name)
                    saved_pdf = save_images_as_pdf(images, pdf_path)
                    if saved_pdf:
                        zipf.write(saved_pdf, os.path.basename(saved_pdf))
                        st.success(f"Chapter {chapter} added to ZIP.")
        
        # Provide a link to download the ZIP file
        with open(zip_file_path, "rb") as zipf:
            st.download_button(
                label="Download All Chapters as ZIP",
                data=zipf,
                file_name="manhwa_chapters.zip",
                mime="application/zip",
            )

if __name__ == "__main__":
    main()