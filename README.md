# Podcast Outreach Pro

Windows desktop app for automating podcast outreach via Matchmaker.fm with AI-generated pitches.

## Setup & Build

### Prerequisites
- Python 3.10+ installed ([python.org](https://python.org))
- Google Chrome installed (for browser automation)
- OpenAI API key

### Build the .exe (Windows)
1. Open Command Prompt or PowerShell in this folder
2. Run: `build.bat`
3. The file `PodcastOutreachPro.exe` will appear in the project folder

### Running without building (for development)
```
pip install -r requirements.txt
python main.py
```

## How to Use

### 1. Setup Tab
- Enter your **OpenAI API Key**
- Enter your **Matchmaker.fm email and password**
- Fill in your **business/guest information** — the more detail, the better the pitch
- Click **Save Configuration**

### 2. Pitch Creator Tab
- Click **Generate Pitch** — the AI creates a personalized pitch from your business info
- Edit the pitch directly in the text area
- Use the **Refine Pitch** section: type instructions like *"make it shorter"* or *"add more enthusiasm"* and click Refine
- **Copy to Clipboard** or **Save Pitch**

### 3. Outreach Tab
1. Click **Launch Browser** — Chrome opens to Matchmaker.fm login
2. If your credentials are saved, click **Fill Login & Submit** — or log in manually
3. If a captcha appears, **solve it manually in the browser window**
4. Click **Check Login Status** to confirm you're logged in
5. Select podcast **categories** you want to target
6. Click **Search Podcasts** — the app navigates and scrapes results
7. Browse results, **Open Page** to view a podcast, or **Copy Pitch** to grab your pitch

### 4. Activity Log
- View all timestamped actions for reference

## Notes
- Your config is saved locally in `config.json` (passwords are obfuscated)
- The browser window stays open so you can interact with it manually at any time
- Matchmaker.fm's website structure may change — if scraping breaks, use the browser manually while copying your pitch from the Pitch Creator tab
