import os
import re
import requests
import streamlit as st
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import time

# Streamlit App Title and Description
st.title("FlashFast Manhwa Downloader")
st.subheader("Download chapters of your favorite manhwa as PDF")

# Function to download a single image
def download_image(url, save_dir, image_name, retries=10):
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=100)
            response.raise_for_status()
            image_path = os.path.join(save_dir, image_name)
            with open(image_path, 'wb') as file:
                file.write(response.content)
            return image_path
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                time.sleep(2)  # Retry after a small delay
    return None

# Function to save images as a PDF
def save_images_as_pdf(image_paths, pdf_path):
    try:
        images = [Image.open(img).convert('RGB') for img in image_paths if img]
        if images:
            images[0].save(pdf_path, save_all=True, append_images=images[1:])
            return pdf_path
        else:
            return None
    except Exception as e:
        return None

# Function to fetch and download all images in a chapter
def fetch_and_download_images(chapter_url, save_dir):
    try:
        response = requests.get(chapter_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the 'reading-content' class and extract all image URLs
        reading_content = soup.find(class_="reading-content")
        if not reading_content:
            return []

        image_urls = [
            urljoin(chapter_url, img['src'])
            for img in reading_content.find_all('img')
            if 'src' in img.attrs and img['src'].lower().endswith(('.jpg', '.webp'))
        ]

        # Download images
        image_paths = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(download_image, img_url, save_dir, os.path.basename(img_url))
                for img_url in image_urls
            ]
            for future in futures:
                result = future.result()
                if result:
                    image_paths.append(result)

        return image_paths
    except Exception:
        return []

# Function to save a chapter as a PDF
def save_chapter_as_pdf(base_url, chapter_num, save_dir):
    chapter_url = f"{base_url}/chapter-{chapter_num}/"
    chapter_dir = os.path.join(save_dir, f"chapter-{chapter_num}")
    os.makedirs(chapter_dir, exist_ok=True)

    image_paths = fetch_and_download_images(chapter_url, chapter_dir)
    if image_paths:
        manga_title = base_url.rstrip('/').split('/')[-1]
        pdf_name = f"{manga_title}-Chapter-{chapter_num}.pdf"
        pdf_path = os.path.join(save_dir, pdf_name)
        pdf_result = save_images_as_pdf(image_paths, pdf_path)

        # Clean up images after generating the PDF
        for img in image_paths:
            os.remove(img)

        return pdf_result
    else:
        return None

# Main Streamlit App Logic
base_url = st.text_input("Enter the Base URL (e.g., https://example.com/manga):")
start_chapter = st.number_input("Start Chapter", min_value=1, step=1, format="%d")
end_chapter = st.number_input("End Chapter", min_value=1, step=1, format="%d")

if st.button("Download Chapters"):
    save_dir = "MangaChapters"
    os.makedirs(save_dir, exist_ok=True)

    for chapter_num in range(int(start_chapter), int(end_chapter) + 1):
        pdf_file_path = save_chapter_as_pdf(base_url, chapter_num, save_dir)
        if pdf_file_path:
            with open(pdf_file_path, "rb") as pdf_file:
                st.download_button(
                    label=f"Download Chapter {chapter_num} PDF",
                    data=pdf_file,
                    file_name=os.path.basename(pdf_file_path),
                    mime="application/pdf",
                )