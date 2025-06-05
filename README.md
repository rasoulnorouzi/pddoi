# pddoi

This Streamlit app downloads academic papers using their DOIs. It first tries
several Sci-Hub mirrors and, if none succeed, falls back to the Unpaywall API to
fetch any available open access versions. Upload a text file containing DOIs
separated by commas and the app will attempt to download them and bundle the
results into a ZIP file.
