# 🚰 DWR Well Log Transcriber

A specialized Python tool built with **Streamlit** to streamline the manual transcription of Colorado Department of Water Resources (DWR) well logs into structured datasets for hydrological modeling.

## 🌟 The Problem

Transcribing historical well logs from the DWR database is often a slow, error-prone process involving toggling between inconsistent PDF scans and spreadsheets. This tool creates a unified workspace to accelerate data entry while ensuring high data integrity.

## 🛠️ Key Features

- **Guided Data Import:** Step-by-step instructions walk users through exporting well data from the DWR Well Permit Search and preparing it for upload.
- **Dynamic Link Generation:** Automatically generates a clickable link to the DWR record for each well as you work through the list.
- **Smart Validation Engine:** Prevents submission if depth gaps, overlaps, inverted depths, or interior empty rows are detected. Trailing empty rows are silently ignored, so short logs (e.g. 5 rows) submit without warnings.
- **Auto-Fill Logic:** Two "Auto-Fill Bottoms" buttons (above and below the table) synchronize each row's Bottom Depth with the next row's Top Depth, reducing manual keystrokes.
- **Leading-Zero Protection:** Prefixes Receipt Numbers with `R` and Permit Numbers with `P` to prevent leading zeros from being lost when files are opened in Excel or other spreadsheet software.
- **No Data Logging:** A dedicated "No Data" button records wells with no available log without requiring table entry, and writes them to the master output with a status of `ND`.
- **Undo:** Mistakes happen — the Undo button reverses the most recent submission or No Data entry, restores the table data, and returns you to that well to re-edit and resubmit.
- **Two Structured Outputs:** Data is written to two separate CSVs — one for lithology log intervals and one for well metadata — each downloadable on demand from the sidebar.
- **Real-Time Progress Tracking:** A progress bar and wells-processed counter in the sidebar help manage large-scale transcription sessions.

## 📤 Output Files

| File | Columns | One row per |
|---|---|---|
| `log_output.csv` | Receipt, Top Depth, Bottom Depth, Lithology | Lithology interval |
| `master_output.csv` | Receipt, Permit Number, UTM X, UTM Y, Latitude, Longitude, Notes, Processing Status | Well |

## 📂 Project Structure

- `app.py`: The core Streamlit application logic and UI.
- `requirements.txt`: Python dependencies (Pandas, Openpyxl, Streamlit).
- `.gitignore`: Configured to keep raw DWR data files private and off GitHub.
- `data/`: Local directory for input and output spreadsheets (excluded from version control).

## 📋 Input File Format

The input file should be the data copied from the well attribute table in [DWR Well Permit Search](https://dwr.state.co.us/Tools/WellPermits) and pasted directly into a blank Excel workbook — **no header row**. The app reads the following columns by position:

| Column | Field |
|---|---|
| 1 | Receipt Number |
| 2 | Permit Number |
| 3 | Permit Status |
| 23 | UTM X |
| 24 | UTM Y |
| 25 | Latitude |
| 26 | Longitude |

## 🚀 How to Run

1. **Clone the Repo:**
   ```bash
   git clone https://github.com/dcarney314/dwr-log-transcriber.git
   cd dwr-log-transcriber
   ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Launch the App:**
   ```bash
   streamlit run app.py
   ```

4. **Import your data:** Follow the on-screen instructions to export well data from the DWR website, paste it into Excel, and upload it to the tool.
