import streamlit as st
import requests
from bs4 import BeautifulSoup
import os
import time
import random
from urllib.parse import urlparse
import zipfile
import io
import shutil

# Several Sci-Hub domains occasionally return HTTP 403.  Using a variety
# of user agents and falling back to the r.jina.ai proxy helps bypass this.
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/115.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/15.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/112.0 Safari/537.36",
]


def fetch_with_bypass(url, headers):
    """Fetch a URL and retry via r.jina.ai if a 403 Forbidden is returned."""
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code == 403:
        # r.jina.ai fetches the resource server-side and returns the content
        proxy_url = f"https://r.jina.ai/{url}"
        response = requests.get(proxy_url, headers=headers, timeout=30)
    return response

def clear_papers_directory(output_dir="papers"):
    """Remove the papers directory if it exists."""
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
        st.write("Previous downloads cleared.")

def try_download_with_mirrors(doi, mirrors, output_dir="papers", delay_range=(3, 7)):
    """
    Attempt to download a paper for a given DOI using the provided list of Sci-Hub mirrors.
    Returns True if any mirror succeeds, otherwise False.
    """
    for mirror in mirrors:
        st.write(f"Trying mirror: {mirror}")
        success = download_paper(doi, output_dir=output_dir, sci_hub_url=mirror)
        if success:
            return True
        else:
            st.write(f"Mirror {mirror} failed for DOI: {doi}. Trying next mirror...")
            delay = random.uniform(delay_range[0], delay_range[1])
            st.write(f"Waiting {delay:.2f} seconds before next mirror...")
            time.sleep(delay)
    st.write("All Sci-Hub mirrors failed. Checking open access sources...")
    return download_open_access(doi, output_dir=output_dir)

def download_paper(doi, output_dir="papers", sci_hub_url="https://sci-hub.box/"):
    """
    Download a paper from Sci-Hub using its DOI.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    doi = doi.strip()
    if doi.startswith('https://doi.org/'):
        doi = doi.replace('https://doi.org/', '')
    
    url = f"{sci_hub_url}{doi}"
    
    try:
        headers = {
            'User-Agent': random.choice(USER_AGENTS)
        }
        response = fetch_with_bypass(url, headers)
        
        if response.status_code != 200:
            st.write(f"Failed to access Sci-Hub for DOI: {doi}. Status code: {response.status_code}")
            return False
        
        soup = BeautifulSoup(response.text, 'html.parser')
        pdf_url = None
        
        # Try different methods to find the PDF link
        iframe = soup.find('iframe')
        if iframe and iframe.get('src'):
            pdf_url = iframe.get('src')
        
        if not pdf_url:
            embed = soup.find('embed')
            if embed and embed.get('src'):
                pdf_url = embed.get('src')
        
        if not pdf_url:
            buttons = soup.find_all('a')
            for button in buttons:
                if button.get('href') and button.get('href').endswith('.pdf'):
                    pdf_url = button.get('href')
                    break
        
        if not pdf_url:
            download_div = soup.find('div', id='download')
            if download_div:
                links = download_div.find_all('a')
                for link in links:
                    if link.get('href'):
                        pdf_url = link.get('href')
                        break
        
        if not pdf_url:
            st.write(f"No PDF found for DOI: {doi}")
            return False
        
        # Handle relative URLs
        if pdf_url.startswith('//'):
            pdf_url = 'https:' + pdf_url
        elif not pdf_url.startswith(('http://', 'https://')):
            parsed_url = urlparse(sci_hub_url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            pdf_url = base_url + pdf_url if pdf_url.startswith('/') else base_url + '/' + pdf_url
        
        st.write(f"Downloading PDF from: {pdf_url}")
        pdf_response = fetch_with_bypass(pdf_url, headers)
        
        if pdf_response.status_code != 200:
            st.write(f"Failed to download PDF for DOI: {doi}. Status code: {pdf_response.status_code}")
            return False
        
        content_type = pdf_response.headers.get('Content-Type', '')
        if 'application/pdf' not in content_type and not pdf_url.endswith('.pdf'):
            st.write(f"Warning: Content may not be a PDF for DOI: {doi}.")
        
        safe_doi = doi.replace('/', '_').replace('\\', '_')
        filename = os.path.join(output_dir, f"{safe_doi}.pdf")
        
        with open(filename, 'wb') as f:
            f.write(pdf_response.content)
        
        if os.path.getsize(filename) < 10000:
            st.write(f"Warning: Downloaded file for DOI {doi} is very small ({os.path.getsize(filename)} bytes)")
            with open(filename, 'rb') as f:
                content_start = f.read(1000).decode('utf-8', errors='ignore')
                if '<html' in content_start.lower() or '<!doctype html' in content_start.lower():
                    st.write("Error: Downloaded file appears to be HTML, not a PDF")
                    os.remove(filename)
                    return False
        
        st.write(f"**Successfully downloaded:** `{filename}`")
        return True
    
    except Exception as e:
        st.write(f"Error downloading paper with DOI {doi}: {str(e)}")
        return False

def download_open_access(doi, output_dir="papers", email="example@example.com"):
    """
    Attempt to download an open access version of the paper using the Unpaywall API.
    """
    api_url = f"https://api.unpaywall.org/v2/{doi}?email={email}"
    try:
        res = requests.get(api_url, timeout=30)
        if res.status_code != 200:
            st.write(f"Unpaywall request failed for DOI: {doi}. Status code: {res.status_code}")
            return False
        data = res.json()
        pdf_url = None
        if data.get("best_oa_location") and data["best_oa_location"].get("url_for_pdf"):
            pdf_url = data["best_oa_location"]["url_for_pdf"]
        elif data.get("oa_locations"):
            for loc in data["oa_locations"]:
                if loc.get("url_for_pdf"):
                    pdf_url = loc["url_for_pdf"]
                    break
        if not pdf_url:
            st.write(f"No open access PDF found for DOI: {doi}")
            return False

        headers = {
            'User-Agent': random.choice(USER_AGENTS)
        }
        pdf_response = fetch_with_bypass(pdf_url, headers)
        if pdf_response.status_code != 200:
            st.write(f"Failed to download OA PDF for DOI: {doi}. Status code: {pdf_response.status_code}")
            return False
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        safe_doi = doi.replace('/', '_').replace('\\', '_')
        filename = os.path.join(output_dir, f"{safe_doi}.pdf")
        with open(filename, 'wb') as f:
            f.write(pdf_response.content)
        st.write(f"**Successfully downloaded OA PDF:** `{filename}`")
        return True
    except Exception as e:
        st.write(f"Error downloading OA paper with DOI {doi}: {str(e)}")
        return False

def batch_download(doi_list, mirrors, output_dir="papers", delay_range=(3, 7)):
    """
    Download multiple papers from Sci-Hub using their DOIs and a list of mirrors.
    Returns (successful_dois, failed_dois).
    """
    successful_dois = []
    failed_dois = []

    progress_bar = st.progress(0)
    
    for i, doi in enumerate(doi_list):
        with st.spinner(f"Processing {i+1}/{len(doi_list)}: {doi}..."):
            st.write("---")
            st.write(f"**DOI {i+1}/{len(doi_list)}:** `{doi}`")
            success = try_download_with_mirrors(doi, mirrors, output_dir=output_dir, delay_range=delay_range)
            if success:
                successful_dois.append(doi)
            else:
                failed_dois.append(doi)
        progress_bar.progress(int((i+1)/len(doi_list)*100))
    
    return successful_dois, failed_dois

def zip_papers(output_dir="papers"):
    """
    Create a zip archive of the downloaded PDFs.
    Returns the bytes of the zip file.
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for foldername, subfolders, filenames in os.walk(output_dir):
            for filename in filenames:
                file_path = os.path.join(foldername, filename)
                zip_file.write(file_path, arcname=filename)
    zip_buffer.seek(0)
    return zip_buffer

def failed_dois_file(failed_list):
    """
    Create a text file (in-memory) listing the failed DOIs.
    Returns the bytes of the text file.
    """
    failed_str = "\n".join(failed_list)
    txt_buffer = io.BytesIO(failed_str.encode('utf-8'))
    return txt_buffer

def main():
    st.title("Sci-Hub Paper Downloader")
    st.markdown(
        """
        This app downloads papers from Sci-Hub by uploading a text file containing DOIs (comma-separated).
        You can choose default Sci-Hub mirrors or add your own.
        
        **Process:**  
        1. Each DOI is tried against all provided mirrors sequentially.  
        2. If one mirror fails, the next is tried automatically.  
        3. Downloaded PDFs are zipped for easy download.  
        4. A separate file lists DOIs for which downloads failed.
        """
    )
    
    # Reset button: Clear previous downloads and restart the app
    if st.button("Reset / Start New Process"):
        clear_papers_directory("papers")
        for key in ["zip_buffer", "failed_buffer", "download_summary", "total_dois", "success_count", "failed_count"]:
            if key in st.session_state:
                del st.session_state[key]
        try:
            st.experimental_rerun()
        except AttributeError:
            st.info("Reset successful. Please refresh the page manually.")
    
    uploaded_file = st.file_uploader("Upload a text file with DOIs (comma-separated)", type=["txt"])
    
    # Default Sci-Hub mirrors
    default_mirrors = [
        "https://sci-hub.box/",
        "https://sci-hub.se/",
        "https://sci-hub.wf/"
    ]
    
    st.subheader("Select or Add Sci-Hub Mirrors")
    selected_defaults = st.multiselect("Choose default Sci-Hub mirrors", default_mirrors, default=default_mirrors)
    custom_mirrors = st.text_area("Or add custom Sci-Hub mirrors (one per line)", value="")
    custom_mirrors_list = [mirror.strip() for mirror in custom_mirrors.splitlines() if mirror.strip()]

    # Combine and deduplicate mirrors, then enforce a maximum of three
    all_mirrors = list(dict.fromkeys(selected_defaults + custom_mirrors_list))
    if not all_mirrors:
        all_mirrors = default_mirrors
    if len(all_mirrors) > 3:
        st.warning("Only the first three mirrors will be used.")
        all_mirrors = all_mirrors[:3]
    
    delay_range = st.slider("Select delay range between requests (in seconds)", 1, 10, (3, 7))
    
    if st.button("Download Papers"):
        if uploaded_file is not None:
            try:
                content = uploaded_file.read().decode("utf-8")
                doi_list = [doi.strip().strip('"') for doi in content.split(",") if doi.strip()]
                st.write(f"Found {len(doi_list)} DOIs.")
                st.session_state.total_dois = len(doi_list)
                
                successful, failed = batch_download(
                    doi_list=doi_list,
                    mirrors=all_mirrors,
                    output_dir="papers",
                    delay_range=delay_range
                )
                
                st.session_state.success_count = len(successful)
                st.session_state.failed_count = len(failed)
                
                # Store download buffers in session state
                if successful:
                    st.session_state.zip_buffer = zip_papers()
                else:
                    st.session_state.zip_buffer = None
                
                if failed:
                    st.session_state.failed_buffer = failed_dois_file(failed)
                else:
                    st.session_state.failed_buffer = None
                
                # Create a detailed summary report
                summary = (
                    f"**Total DOIs Processed:** {st.session_state.total_dois}\n\n"
                    f"**Successful Downloads:** {st.session_state.success_count}\n\n"
                    f"**Failed Downloads:** {st.session_state.failed_count}\n\n"
                )
                if st.session_state.failed_count > 0:
                    summary += f"**Failed DOIs:** {', '.join(failed)}\n"
                st.session_state.download_summary = summary
                
            except Exception as e:
                st.error(f"Error processing file: {str(e)}")
        else:
            st.warning("Please upload a text file with DOIs.")
    
    # Display the download buttons and summary if available in session state
    if "zip_buffer" in st.session_state or "failed_buffer" in st.session_state:
        with st.container():
            st.write("---")
            st.subheader("Download Files")
            col1, col2 = st.columns(2)
            with col1:
                if st.session_state.get("zip_buffer"):
                    st.download_button(
                        label="Download All Papers as Zip",
                        data=st.session_state.zip_buffer,
                        file_name="downloaded_papers.zip",
                        mime="application/zip",
                        key="download_zip"
                    )
                else:
                    st.info("No successful downloads available.")
            with col2:
                if st.session_state.get("failed_buffer"):
                    st.download_button(
                        label="Download Failed DOIs List",
                        data=st.session_state.failed_buffer,
                        file_name="failed_dois.txt",
                        mime="text/plain",
                        key="download_failed"
                    )
                else:
                    st.info("No failed downloads.")
    
        # Display the detailed summary report
        if "download_summary" in st.session_state:
            st.write("---")
            st.subheader("Download Summary")
            st.markdown(st.session_state.download_summary)
    
    # Celebratory animation if there are successful downloads
    if st.session_state.get("zip_buffer"):
        st.balloons()

if __name__ == "__main__":
    main()
