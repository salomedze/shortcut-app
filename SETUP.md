# არქი — Setup Guide

## Step 1: Install Python

1. Go to https://www.python.org/downloads/
2. Download Python 3.11 or newer
3. During install, check the box **"Add Python to PATH"**
4. Verify: open Terminal and type `python --version` — you should see a version number

---

## Step 2: Get your Anthropic API key

1. Go to https://console.anthropic.com
2. Create an account
3. Go to **API Keys** → **Create Key**
4. Copy the key (starts with `sk-ant-...`)

---

## Step 3: Set up the project

Open Terminal (or Command Prompt) and run these commands one by one:

```bash
# Go to the project folder
cd C:\Users\PCARCH\georgian-arch-agent

# Install all required libraries (takes a few minutes)
pip install -r requirements.txt
```

---

## Step 4: Add your API key

1. In the project folder, find the file `.env.example`
2. Copy it and rename the copy to `.env`
3. Open `.env` and replace `your_api_key_here` with your actual API key:
   ```
   ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxx
   ```

---

## Step 5: Add your regulation documents

1. Put your PDF files into the `docs/` folder inside the project
2. Run the ingestion script to index them:
   ```bash
   python ingest.py
   ```
   This only needs to be done once (or when you add new documents).

---

## Step 6: Start the app

```bash
streamlit run app.py
```

The app will open automatically in your browser at http://localhost:8501

---

## Step 7: Use it

- Type questions in Georgian in the chat box
- Use the sidebar to upload new PDF documents at any time
- Click example questions in the sidebar to get started

---

## Deploying online (so others can use it)

1. Create a free account at https://github.com
2. Create a free account at https://streamlit.io/cloud
3. Upload the project to GitHub
4. Connect it to Streamlit Cloud — it will be live at a public URL

*(We can do this step together when the app is working well locally)*
