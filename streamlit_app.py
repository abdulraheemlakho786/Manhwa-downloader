import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import streamlit as st

# Regex pattern to match filenames with numeric or custom patterns
IMAGE_PATTERN = re.compile(r".*[/\\](\d{1,10}(-\w+)?)(\.\w+)$")


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
            st.warning(f"Attempt {attempt + 1} failed for {image_name}: {e}")
            if attempt < retries - 1:
                continue
    st.error(f"Failed to download {image_name} after {retries} attempts. Skipping.")
    return None


def save_images_as_pdf(image_paths, pdf_path):
    """Save downloaded images as a PDF, splitting pages if needed."""
    try:
        images = [Image.open(img).convert('RGB') for img in image_paths if img]
        if not images:
            st.warning("No images to include in PDF.")
            return

        # Max dimensions for a single PDF page
        max_width = max(img.width for img in images)
        max_pixels_per_page = 65500

        pdf_pages = []
        current_page = Image.new("RGB", (max_width, max_pixels_per_page), color=(255, 255, 255))
        y_offset = 0

        for img in images:
            if img.height > max_pixels_per_page:
                # Split oversized images into smaller parts
                for top in range(0, img.height, max_pixels_per_page):
                    part = img.crop((0, top, img.width, min(top + max_pixels_per_page, img.height)))
                    if y_offset + part.height > max_pixels_per_page:
                        # Save the current page and start a new one
                        pdf_pages.append(current_page)
                        current_page = Image.new("RGB", (max_width, max_pixels_per_page), color=(255, 255, 255))
                        y_offset = 0

                    current_page.paste(part, (0, y_offset))
                    y_offset += part.height
            else:
                if y_offset + img.height > max_pixels_per_page:
                    # Save the current page and start a new one
                    pdf_pages.append(current_page)
                    current_page = Image.new("RGB", (max_width, max_pixels_per_page), color=(255, 255, 255))
                    y_offset = 0

                current_page.paste(img, (0, y_offset))
                y_offset += img.height

        # Add the last page
        if y_offset > 0:
            pdf_pages.append(current_page)

        # Save all pages as a multi-page PDF
        pdf_pages[0].save(pdf_path, save_all=True, append_images=pdf_pages[1:])
        st.success(f"PDF created: {pdf_path}")
        return pdf_path
    except Exception as e:
        st.error(f"Error creating PDF: {e}")
        return None


def fetch_and_download_images(chapter_url, save_dir):
    try:
        response = requests.get(chapter_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the 'reading-content' class and extract all image URLs within it
        reading_content = soup.find(class_="reading-content")
        if not reading_content:
            st.error(f"'reading-content' class not found for {chapter_url}")
            return []

        image_urls = [
            urljoin(chapter_url, img['src'])
            for img in reading_content.find_all('img')
            if 'src' in img.attrs and img['src'].lower().endswith(('.jpg', '.webp', '.png'))
        ]

        if not image_urls:
            st.error(f"No images found in 'reading-content' for {chapter_url}")
            return []

        # Download images concurrently with progress bar
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
    except Exception as e:
        st.error(f"Error processing chapter: {e}")
        return []


def save_chapter_as_pdf(base_url, chapter_num, save_dir):
    chapter_url = f"{base_url}/chapter-{chapter_num}/"
    chapter_dir = os.path.join(save_dir, f"chapter-{chapter_num}")
    os.makedirs(chapter_dir, exist_ok=True)

    st.info(f"Fetching images for Chapter {chapter_num}...")
    image_paths = fetch_and_download_images(chapter_url, chapter_dir)
    if image_paths:
        # Extract the manga title from the base URL
        manga_title = base_url.rstrip('/').split('/')[-1]
        pdf_name = f"{manga_title}-Chapter-{chapter_num}.pdf"
        pdf_path = os.path.join(save_dir, pdf_name)
        save_images_as_pdf(image_paths, pdf_path)

        # Clean up downloaded images after PDF generation
        for img in image_paths:
            try:
                os.remove(img)
            except OSError as e:
                st.error(f"Error deleting file {img}: {e}")

        st.success(f"Chapter {chapter_num} saved as PDF!")
    else:
        st.warning(f"No images downloaded for Chapter {chapter_num}.")


# Streamlit App Interface
st.title("📚 FlashFast Manhwa Downloader")

base_url = st.text_input("Enter the base URL of the manhwa (e.g., https://example.com/manga):")
start_chapter = st.number_input("Enter the starting chapter number:", min_value=1, step=1)
end_chapter = st.number_input("Enter the ending chapter number:", min_value=1, step=1)
save_dir = "/tmp/ManhwaChapters"

if st.button("Download Chapters"):
    if not base_url:
        st.error("Please enter a valid base URL.")
    elif start_chapter > end_chapter:
        st.error("Starting chapter cannot be greater than ending chapter.")
    else:
        os.makedirs(save_dir, exist_ok=True)
        all_chapters = range(start_chapter, end_chapter + 1)
        for chapter in all_chapters:
            save_chapter_as_pdf(base_url, chapter, save_dir)

        st.success("All chapters downloaded successfully!")