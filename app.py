vimport os
import re
import requests
import streamlit as st
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import time

# Streamlit App Title
st.title("FlashFast Manhwa Downloader")
st.subheader("Download chapters of your favorite manhwa as PDF")

# Function to download an image
def download_image(url, save_dir, image_name, retries=10):
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            image_path = os.path.join(save_dir, image_name)
            with open(image_path, "wb") as file:
                file.write(response.content)
            return image_path
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                st.error(f"Failed to download {image_name} after {retries} attempts.")
    return None

# Function to save images as a PDF
def save_images_as_pdf(image_paths, pdf_path):
    try:
        images = [Image.open(img).convert("RGB") for img in image_paths if img]
        if images:
            images[0].save(pdf_path, save_all=True, append_images=images[1:])
            st.success(f"PDF created: {pdf_path}")
        else:
            st.error("No images to include in PDF.")
    except Exception as e:
        st.error(f"Error creating PDF: {e}")

# Function to fetch and download images from a chapter URL
def fetch_and_download_images(chapter_url, save_dir):
    try:
        response = requests.get(chapter_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Locate images in the reading-content section
        reading_content = soup.find(class_="reading-content")
        if not reading_content:
            st.error(f"'reading-content' class not found at {chapter_url}")
            return []

        image_urls = [
            urljoin(chapter_url, img["src"])
            for img in reading_content.find_all("img")
            if "src" in img.attrs and img["src"].lower().endswith((".jpg", ".webp"))
        ]

        if not image_urls:
            st.warning(f"No images found in 'reading-content' at {chapter_url}")
            return []

        image_paths = []
        for img_url in image_urls:
            image_name = os.path.basename(img_url)
            img_path = download_image(img_url, save_dir, image_name)
            if img_path:
                image_paths.append(img_path)

        return image_paths
    except Exception as e:
        st.error(f"Error processing chapter: {e}")
        return []

# Function to save a chapter as a PDF
def save_chapter_as_pdf(base_url, chapter_num, save_dir):
    chapter_url = f"{base_url}/chapter-{chapter_num}/"
    chapter_dir = os.path.join(save_dir, f"chapter-{chapter_num}")
    os.makedirs(chapter_dir, exist_ok=True)

    st.info(f"Processing Chapter {chapter_num}...")
    start_time = time.time()
    image_paths = fetch_and_download_images(chapter_url, chapter_dir)
    if image_paths:
        pdf_name = f"Chapter-{chapter_num}.pdf"
        pdf_path = os.path.join(save_dir, pdf_name)
        save_images_as_pdf(image_paths, pdf_path)

        # Clean up downloaded images
        for img in image_paths:
            os.remove(img)

        # Remove empty chapter directory
        if os.path.exists(chapter_dir) and not os.listdir(chapter_dir):
            os.rmdir(chapter_dir)

        st.success(f"Chapter {chapter_num} processed successfully!")
    else:
        st.warning(f"No images downloaded for Chapter {chapter_num}.")

    elapsed_time = time.time() - start_time
    st.info(f"Chapter {chapter_num} completed in {elapsed_time:.2f} seconds.")

# Main Logic for Streamlit App
base_url = st.text_input("Enter the Base URL (e.g., https://example.com/manga):")
start_chapter = st.number_input("Start Chapter", min_value=1, step=1, format="%d")
end_chapter = st.number_input("End Chapter", min_value=1, step=1, format="%d")

if st.button("Download Chapters"):
    if not base_url or start_chapter > end_chapter:
        st.error("Please enter a valid Base URL and chapter range.")
    else:
        save_dir = "MangaChapters"
        os.makedirs(save_dir, exist_ok=True)
        for chapter_num in range(int(start_chapter), int(end_chapter) + 1):
            save_chapter_as_pdf(base_url, chapter_num, save_dir)
        st.success("All chapters downloaded successfully!")