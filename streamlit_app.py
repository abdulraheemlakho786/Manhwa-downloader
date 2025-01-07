import os
import re
import requests
import streamlit as st
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import shutil
import time

# Create a folder to save files
save_dir = "MangaChapters"
os.makedirs(save_dir, exist_ok=True)

# Streamlit UI
st.title("FlashFast Manhwa Downloader")
st.subheader("Download chapters of your favorite manhwa as PDF!")

# Clear previous files
def clear_directory(directory):
    if os.path.exists(directory):
        shutil.rmtree(directory)
    os.makedirs(directory, exist_ok=True)

# Download a single image
def download_image(url, save_dir, image_name, retries=5):
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            image_path = os.path.join(save_dir, image_name)
            with open(image_path, "wb") as file:
                file.write(response.content)
            return image_path
        except requests.exceptions.RequestException:
            if attempt < retries - 1:
                time.sleep(2)  # Retry delay
    return None

# Combine images into a PDF
def save_images_as_pdf(image_paths, pdf_path):
    try:
        images = [Image.open(img).convert("RGB") for img in image_paths if img]
        if not images:
            return None

        images[0].save(pdf_path, save_all=True, append_images=images[1:])
        return pdf_path
    except Exception as e:
        st.error(f"Error creating PDF: {e}")
        return None

# Fetch images from the chapter page
def fetch_images(chapter_url):
    try:
        response = requests.get(chapter_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        reading_content = soup.find(class_="reading-content")
        if not reading_content:
            st.error(f"No 'reading-content' found at {chapter_url}")
            return []

        image_urls = [
            urljoin(chapter_url, img["src"])
            for img in reading_content.find_all("img")
            if "src" in img.attrs and img["src"].lower().endswith((".jpg", ".png", ".webp"))
        ]
        return image_urls
    except Exception as e:
        st.error(f"Error fetching images: {e}")
        return []

# Download and process a single chapter
def process_chapter(base_url, chapter_num):
    chapter_url = f"{base_url}/chapter-{chapter_num}/"
    chapter_dir = os.path.join(save_dir, f"chapter-{chapter_num}")
    os.makedirs(chapter_dir, exist_ok=True)

    image_urls = fetch_images(chapter_url)
    if not image_urls:
        st.error(f"No images found for Chapter {chapter_num}")
        return None

    st.write(f"Downloading Chapter {chapter_num} ({len(image_urls)} images)...")
    image_paths = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(download_image, url, chapter_dir, os.path.basename(url))
            for url in image_urls
        ]
        for future in futures:
            result = future.result()
            if result:
                image_paths.append(result)

    # Save chapter as PDF
    pdf_name = f"Chapter-{chapter_num}.pdf"
    pdf_path = os.path.join(save_dir, pdf_name)
    pdf_file = save_images_as_pdf(image_paths, pdf_path)

    # Cleanup images
    for img in image_paths:
        os.remove(img)
    os.rmdir(chapter_dir)

    return pdf_file

# Streamlit inputs
base_url = st.text_input("Enter the Base URL (e.g., https://example.com/manga):")
start_chapter = st.number_input("Start Chapter", min_value=1, step=1)
end_chapter = st.number_input("End Chapter", min_value=1, step=1)

if st.button("Download Chapters"):
    if not base_url:
        st.error("Please enter a valid Base URL.")
    elif start_chapter > end_chapter:
        st.error("End Chapter must be greater than or equal to Start Chapter.")
    else:
        clear_directory(save_dir)
        pdf_files = []

        for chapter in range(int(start_chapter), int(end_chapter) + 1):
            pdf_file = process_chapter(base_url, chapter)
            if pdf_file:
                pdf_files.append(pdf_file)

        if pdf_files:
            st.success("Chapters downloaded successfully!")
            for pdf_file in pdf_files:
                with open(pdf_file, "rb") as file:
                    st.download_button(
                        label=f"Download {os.path.basename(pdf_file)}",
                        data=file,
                        file_name=os.path.basename(pdf_file),
                        mime="application/pdf",
                    )
        else:
            st.error("No chapters were downloaded.")