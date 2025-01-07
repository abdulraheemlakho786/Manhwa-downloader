import os
import re
import requests
import streamlit as st
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import time
import shutil

# Streamlit app UI
st.title("FlashFast Manhwa Downloader")
st.subheader("Download chapters of your favorite manhwa as PDF")

# Directory to save files
save_dir = "MangaChapters"

# Function to clear old files
def clear_directory(directory):
    if os.path.exists(directory):
        shutil.rmtree(directory)
    os.makedirs(directory, exist_ok=True)

# Function to download an image
def download_image(url, save_dir, image_name, retries=10):
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=100)
            response.raise_for_status()
            image_path = os.path.join(save_dir, image_name)
            with open(image_path, "wb") as file:
                file.write(response.content)
            return image_path
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                time.sleep(2)  # Retry delay
    return None

# Function to save images as PDF
def save_images_as_pdf(image_paths, pdf_path):
    images = [Image.open(img).convert("RGB") for img in image_paths if img]
    if not images:
        return None

    max_width = max(img.width for img in images)
    max_pixels_per_page = 65500
    pdf_pages = []
    current_page = Image.new("RGB", (max_width, max_pixels_per_page), color=(255, 255, 255))
    y_offset = 0

    for img in images:
        if y_offset + img.height > max_pixels_per_page:
            pdf_pages.append(current_page)
            current_page = Image.new("RGB", (max_width, max_pixels_per_page), color=(255, 255, 255))
            y_offset = 0
        current_page.paste(img, (0, y_offset))
        y_offset += img.height

    if y_offset > 0:
        pdf_pages.append(current_page)

    pdf_pages[0].save(pdf_path, save_all=True, append_images=pdf_pages[1:])
    return pdf_path

# Function to fetch and download images
def fetch_and_download_images(chapter_url, save_dir):
    response = requests.get(chapter_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    reading_content = soup.find(class_="reading-content")
    if not reading_content:
        return []

    image_urls = [
        urljoin(chapter_url, img["src"])
        for img in reading_content.find_all("img")
        if "src" in img.attrs and img["src"].lower().endswith((".jpg", ".webp"))
    ]

    image_paths = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(download_image, img_url, save_dir, os.path.basename(img_url))
            for img_url in image_urls
        ]
        for future in tqdm(futures, desc="Downloading Images", unit="file"):
            result = future.result()
            if result:
                image_paths.append(result)

    return image_paths

# Function to save a chapter as a PDF
def save_chapter_as_pdf(base_url, chapter_num, save_dir):
    chapter_url = f"{base_url}/chapter-{chapter_num}/"
    chapter_dir = os.path.join(save_dir, f"chapter-{chapter_num}")
    os.makedirs(chapter_dir, exist_ok=True)

    image_paths = fetch_and_download_images(chapter_url, chapter_dir)
    if image_paths:
        manga_title = base_url.rstrip("/").split("/")[-1]
        pdf_name = f"{manga_title}-Chapter-{chapter_num}.pdf"
        pdf_path = os.path.join(save_dir, pdf_name)
        pdf_file = save_images_as_pdf(image_paths, pdf_path)

        # Clean up images
        for img in image_paths:
            os.remove(img)
        os.rmdir(chapter_dir)

        return pdf_file
    return None

# Streamlit logic
base_url = st.text_input("Enter the Base URL (e.g., https://example.com/manga):")
start_chapter = st.number_input("Start Chapter", min_value=1, step=1, format="%d")
end_chapter = st.number_input("End Chapter", min_value=1, step=1, format="%d")

if st.button("Download Chapters"):
    clear_directory(save_dir)  # Clear old files
    pdf_files = []

    for chapter_num in range(int(start_chapter), int(end_chapter) + 1):
        st.write(f"Processing Chapter {chapter_num}...")
        pdf_file = save_chapter_as_pdf(base_url, chapter_num, save_dir)
        if pdf_file:
            pdf_files.append(pdf_file)

    if pdf_files:
        st.success("Chapters downloaded successfully!")
        for pdf in pdf_files:
            st.write(f"Download {os.path.basename(pdf)}")
            with open(pdf, "rb") as file:
                st.download_button(
                    label=f"Download {os.path.basename(pdf)}",
                    data=file,
                    file_name=os.path.basename(pdf),
                    mime="application/pdf",
                )
    else:
        st.error("No chapters were downloaded. Please check the URL or chapters.")