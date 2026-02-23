# 🚰 DWR Well Log Transcriber

A specialized Python tool built with **Streamlit** to streamline the manual transcription of Colorado Department of Water Resources (DWR) well logs into structured datasets for hydrological modeling.

## 🌟 The Problem
Transcribing historical well logs from the DWR database is often a slow, error-prone process involving toggling between inconsistent PDF scans and spreadsheets. This tool creates a unified workspace to accelerate data entry while ensuring high data integrity.

## 🛠️ Key Features
- **Dynamic Link Generation:** Automatically generates clickable links to DWR records based on Receipt Numbers.
- **Smart Validation Engine:** Prevents submission if depth gaps, overlaps, or non-numeric values are detected.
- **Auto-Fill Logic:** Synchronizes 'Bottom Depth' with the subsequent row's 'Top Depth' to reduce manual keystrokes.
- **Leading-Zero Protection:** Prefixes IDs with 'R' to ensure data stays intact when exported to Excel/CSV.
- **Real-Time Progress Tracking:** Visual status bars and session previews to manage large-scale data logging.

## 📂 Project Structure
- `app.py`: The core Streamlit application logic and UI.
- `requirements.txt`: Python dependencies (Pandas, Openpyxl, Streamlit).
- `.gitignore`: Configured to keep raw DWR data files private and off GitHub.
- `data/`: Local directory for master and output spreadsheets (excluded from version control).

## 🚀 How to Run
1. **Clone the Repo:**
   ```bash
   git clone [https://github.com/dcarney314/dwr-log-transcriber.git](https://github.com/dcarney314/dwr-log-transcriber.git)
   cd dwr-log-transcriber
2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
3. **Launch the App**
   ```bash
   streamlit run app.py
