import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import time
import streamlit as st
import tempfile

# Streamlit App Title
st.title("FlashFast Manhwa Downloader")
st.subheader("Download chapters of your favorite manhwa as PDF")

# Regex pattern to match filenames
IMAGE_PATTERN = re.compile(r".*[/\\](\d{1,10}(-\w+)?)(\.\w+)$")

def download_image(url, temp_dir, image_name, retries=10):
    """Download a single image."""
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=100)
            response.raise_for_status()
            image_path = os.path.join(temp_dir, image_name)
            with open(image_path, 'wb') as file:
                file.write(response.content)
            return image_path
        except requests.exceptions.RequestException as e:
            st.warning(f"Attempt {attempt + 1} failed for {image_name}: {e}")
            if attempt < retries - 1:
                time.sleep(2)
                continue
    st.error(f"Failed to download {image_name} after {retries} attempts.")
    return None

def save_images_as_pdf(image_paths, pdf_path):
    """Save downloaded images as a single PDF."""
    try:
        images = [Image.open(img).convert('RGB') for img in image_paths if img]
        if not images:
            st.warning("No images to include in PDF.")
            return None

        images[0].save(pdf_path, save_all=True, append_images=images[1:])
        st.success(f"PDF created: {pdf_path}")
        return pdf_path
    except Exception as e:
        st.error(f"Error creating PDF: {e}")
        return None

def fetch_and_download_images(chapter_url, temp_dir):
    """Fetch and download all images from a chapter."""
    try:
        response = requests.get(chapter_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        reading_content = soup.find(class_="reading-content")
        if not reading_content:
            st.error(f"'reading-content' class not found for {chapter_url}")
            return []

        image_urls = [
            urljoin(chapter_url, img['src'])
            for img in reading_content.find_all('img')
            if 'src' in img.attrs and img['src'].lower().endswith(('.jpg', '.webp'))
        ]

        if not image_urls:
            st.warning(f"No images found in 'reading-content' for {chapter_url}")
            return []

        st.info(f"Found {len(image_urls)} images. Downloading...")
        image_paths = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(download_image, img_url, temp_dir, os.path.basename(img_url))
                for img_url in image_urls
            ]
            for future in futures:
                result = future.result()
                if result:
                    image_paths.append(result)

        return image_paths
    except Exception as e:
        st.error(f"Error processing chapter: {e}")
        return []

def save_chapter_as_pdf(base_url, chapter_num, temp_dir):
    """Process a single chapter and save it as a PDF."""
    chapter_url = f"{base_url}/chapter-{chapter_num}/"
    st.info(f"Fetching images for Chapter {chapter_num}...")
    start_time = time.time()
    image_paths = fetch_and_download_images(chapter_url, temp_dir)
    if image_paths:
        pdf_name = f"Chapter-{chapter_num}.pdf"
        pdf_path = os.path.join(temp_dir, pdf_name)
        result_path = save_images_as_pdf(image_paths, pdf_path)

        end_time = time.time()
        st.success(f"Chapter {chapter_num} processed in {end_time - start_time:.2f} seconds.")
        return result_path
    else:
        st.warning(f"No images downloaded for Chapter {chapter_num}.")
        return None

# Main Streamlit Logic
base_url = st.text_input("Enter the base URL of the manhwa (e.g., https://example.com/manga):")
start_chapter = st.number_input("Start Chapter", min_value=1, step=1, format="%d")
end_chapter = st.number_input("End Chapter", min_value=1, step=1, format="%d")

if st.button("Download Chapters"):
    if not base_url:
        st.error("Please enter a valid base URL.")
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            for chapter_num in range(int(start_chapter), int(end_chapter) + 1):
                pdf_file_path = save_chapter_as_pdf(base_url, chapter_num, temp_dir)
                if pdf_file_path:
                    with open(pdf_file_path, "rb") as pdf_file:
                        st.download_button(
                            label=f"Download Chapter {chapter_num} PDF",
                            data=pdf_file,
                            file_name=os.path.basename(pdf_file_path),
                            mime="application/pdf",
                        )