# pddoi

This Streamlit app downloads academic papers using their DOIs. It first tries
up to three Sci-Hub mirrors and, if none succeed, falls back to the Unpaywall API to
fetch any available open access versions. Upload a text file containing DOIs
separated by commas and the app will attempt to download them and bundle the
results into a ZIP file.

## Default Sci-Hub Mirrors

The app ships with three pre-configured mirrors which have been found to be more
reliable. You can replace them or add your own within the app, but only the
first three will be used during a download session. If a mirror responds with
`403 Forbidden`, the request is automatically retried through the `r.jina.ai`
proxy to bypass simple blocking.

```
https://sci-hub.box/
https://sci-hub.se/
https://sci-hub.wf/
```


Run using the following Colab link:
https://colab.research.google.com/drive/1xxKl_oIMaclLqyIsudqeGS3kC2IrWC5R?usp=sharing
