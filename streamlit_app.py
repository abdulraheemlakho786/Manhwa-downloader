import os
import re
import requests
import zipfile
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
from tqdm import tqdm

st.title("FlashFast Manhwa Downloader")
st.subheader("Download chapters of your favorite manhwa as PDF or ZIP")

# Function to download an image
def download_image(url, save_dir, image_name, retries=5):
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            image_path = os.path.join(save_dir, image_name)
            with open(image_path, 'wb') as file:
                file.write(response.content)
            return image_path
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                continue
    return None

# Function to save images as a single PDF
def save_images_as_pdf(image_paths, pdf_path):
    images = [Image.open(img).convert('RGB') for img in image_paths if img]
    if not images:
        return None
    images[0].save(pdf_path, save_all=True, append_images=images[1:])
    return pdf_path

# Function to fetch image URLs from a chapter page
def fetch_images(chapter_url):
    try:
        response = requests.get(chapter_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        reading_content = soup.find(class_="reading-content")
        if not reading_content:
            return []
        image_urls = [
            urljoin(chapter_url, img['src'])
            for img in reading_content.find_all('img')
            if 'src' in img.attrs
        ]
        return image_urls
    except Exception:
        return []

# Function to process a single chapter
def process_chapter(base_url, chapter_num, save_dir):
    chapter_url = f"{base_url}/chapter-{chapter_num}/"
    chapter_dir = os.path.join(save_dir, f"chapter-{chapter_num}")
    os.makedirs(chapter_dir, exist_ok=True)

    image_urls = fetch_images(chapter_url)
    if not image_urls:
        return None

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

    # Extract manga title from the base URL
    manga_title = base_url.rstrip('/').split('/')[-1].replace('-', ' ').title()

    # Save images as a PDF
    pdf_name = f"{manga_title}-Chapter-{chapter_num}.pdf"
    pdf_path = os.path.join(save_dir, pdf_name)
    pdf_file = save_images_as_pdf(image_paths, pdf_path)

    # Cleanup
    for img in image_paths:
        os.remove(img)
    os.rmdir(chapter_dir)

    return pdf_file

# Function to zip all PDFs
def create_zip(zip_name, files, output_dir):
    zip_path = os.path.join(output_dir, zip_name)
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file in files:
            zipf.write(file, os.path.basename(file))
    return zip_path

# Streamlit app logic
save_dir = "/tmp/manga_chapters"
os.makedirs(save_dir, exist_ok=True)

base_url = st.text_input("Enter the Base URL (e.g., https://example.com/manga):").strip()
start_chapter = st.number_input("Start Chapter", min_value=1, step=1, format="%d")
end_chapter = st.number_input("End Chapter", min_value=1, step=1, format="%d")

if st.button("Download Chapters"):
    if not base_url:
        st.error("Please enter a valid base URL.")
    elif start_chapter > end_chapter:
        st.error("Start Chapter must be less than or equal to End Chapter.")
    else:
        all_pdfs = []
        for chapter_num in range(start_chapter, end_chapter + 1):
            st.write(f"Processing Chapter {chapter_num}...")
            pdf_file = process_chapter(base_url, chapter_num, save_dir)
            if pdf_file:
                all_pdfs.append(pdf_file)
            else:
                st.error(f"Failed to process Chapter {chapter_num}")

        if all_pdfs:
            zip_name = "Manhwa_Chapters.zip"
            zip_path = create_zip(zip_name, all_pdfs, save_dir)
            st.success("All chapters processed successfully!")
            with open(zip_path, "rb") as zip_file:
                st.download_button(
                    label="Download All Chapters as ZIP",
                    data=zip_file,
                    file_name=zip_name,
                    mime="application/zip",
                )

        # Cleanup after generating ZIP
        for pdf in all_pdfs:
            os.remove(pdf)