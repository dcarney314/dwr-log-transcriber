import streamlit as st
import pandas as pd
import io

# --- INITIAL SETUP ---
st.set_page_config(layout="wide", page_title="DWR Well Log Transcriber")

# Initialize session state
if 'master_df' not in st.session_state:
    st.session_state.master_df = None
if 'log_data' not in st.session_state:
    st.session_state.log_data = pd.DataFrame([{"Top Depth": None, "Bottom Depth": None, "Lithology": ""}] * 15)
if 'output_df' not in st.session_state:
    st.session_state.output_df = pd.DataFrame(columns=['Receipt', 'Top Depth', 'Bottom Depth', 'Lithology'])
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0

# --- DATA PROCESSING ---
def process_master(df):
    target_indices = [0, 1, 2, 22, 23, 24, 25]
    df = df.iloc[:, target_indices].copy()
    df.columns = ['Receipt', 'Permit Number', 'Permit Status', 'UTM X', 'UTM Y', 'Latitude', 'Longitude']
    df['Receipt'] = 'R' + df['Receipt'].astype(str)
    df['Processing Status'] = 'Pending'
    df['Notes'] = ''
    return df

# --- CALLBACKS (The fix for the refresh issue) ---
def autofill_callback():
    # This function runs BEFORE the page reruns, saving your data
    df = st.session_state.editor_key["edited_rows"]
    # We apply the logic to the existing session state
    for i in range(len(st.session_state.log_data) - 1):
        next_top = st.session_state.log_data.at[i+1, 'Top Depth']
        if pd.notnull(next_top):
            st.session_state.log_data.at[i, 'Bottom Depth'] = next_top

# --- VALIDATION ---
def validate_log(df):
    errors = []
    # Only validate rows that have numerical data
    valid_rows = df[pd.to_numeric(df['Top Depth'], errors='coerce').notnull()]
    
    for i in range(len(valid_rows)):
        row = valid_rows.iloc[i]
        t, b = float(row['Top Depth']), float(row['Bottom Depth'])
        if t >= b:
            errors.append(f"Row {i+1}: Top ({t}) must be less than Bottom ({b}).")
        
        if i < len(valid_rows) - 1:
            next_t = float(valid_rows.iloc[i+1]['Top Depth'])
            if b != next_t:
                errors.append(f"Gap detected: Row {i+1} ends at {b}, next begins at {next_t}.")
    return errors

# --- DIALOGS ---
@st.dialog("Confirm Submission")
def confirm_submit(receipt, notes, data):
    st.write(f"Save log for {receipt}?")
    if st.button("Yes, Submit Log"):
        idx = st.session_state.master_df[st.session_state.master_df['Receipt'] == receipt].index
        st.session_state.master_df.loc[idx, 'Processing Status'] = 'Complete'
        st.session_state.master_df.loc[idx, 'Notes'] = notes
        
        # CLEANING: Delete rows that don't have numerical depths
        clean_data = data.copy()
        clean_data['Top Depth'] = pd.to_numeric(clean_data['Top Depth'], errors='coerce')
        clean_data['Bottom Depth'] = pd.to_numeric(clean_data['Bottom Depth'], errors='coerce')
        clean_data = clean_data.dropna(subset=['Top Depth', 'Bottom Depth'])
        
        clean_data['Receipt'] = receipt
        st.session_state.output_df = pd.concat([st.session_state.output_df, clean_data], ignore_index=True)
        
        # Reset
        st.session_state.log_data = pd.DataFrame([{"Top Depth": None, "Bottom Depth": None, "Lithology": ""}] * 15)
        st.session_state.current_index += 1
        st.rerun()

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚙️ Controls")
    uploaded_file = st.file_uploader("Upload DWR Master Excel", type="xlsx")
    if st.session_state.master_df is not None:
        st.download_button("Download Master", st.session_state.master_df.to_csv(index=False), "master_tracking.csv")
        st.download_button("Download Output", st.session_state.output_df.to_csv(index=False), "well_lithology_data.csv")

# --- MAIN APP ---
if uploaded_file:
    if st.session_state.master_df is None:
        st.session_state.master_df = process_master(pd.read_excel(uploaded_file, header=None))

    receipts = st.session_state.master_df['Receipt'].tolist()
    selected_receipt = st.selectbox("Current Well", receipts, index=st.session_state.current_index)
    st.session_state.current_index = receipts.index(selected_receipt)

    # LINK
    clean_receipt = selected_receipt.lstrip('R')
    st.markdown(f"## 📄 [Open DWR Record {clean_receipt}](https://dwr.state.co.us/Tools/WellPermits/{clean_receipt})")
    
    notes = st.text_input("Notes", value=st.session_state.master_df.loc[st.session_state.master_df['Receipt'] == selected_receipt, 'Notes'].values[0])

    # TABLE & AUTOFILL
    st.subheader("Lithology Entry")
    
    # Autofill Button
    if st.button("⚡ Auto-Fill Bottom Depths"):
        # Explicitly update the dataframe from what is currently in the editor
        for i in range(len(st.session_state.log_data) - 1):
            curr_bottom = st.session_state.log_data.at[i, 'Bottom Depth']
            next_top = st.session_state.log_data.at[i+1, 'Top Depth']
            if pd.notnull(next_top) and (pd.isnull(curr_bottom) or curr_bottom == ""):
                st.session_state.log_data.at[i, 'Bottom Depth'] = next_top
        st.rerun()

    # The Data Editor - Key fix: removed 'Status', added clear key management
    edited_df = st.data_editor(
        st.session_state.log_data,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="log_editor_v3"
    )
    st.session_state.log_data = edited_df

    # SUBMIT
    c1, c2, _ = st.columns([1, 1, 2])
    with c1:
        if st.button("Submit Log", type="primary", use_container_width=True):
            errs = validate_log(st.session_state.log_data)
            if errs:
                for e in errs: st.error(e)
            else:
                confirm_submit(selected_receipt, notes, st.session_state.log_data)
    with c2:
        if st.button("No Data", use_container_width=True):
            # Inline No Data logic for speed
            idx = st.session_state.master_df[st.session_state.master_df['Receipt'] == selected_receipt].index
            st.session_state.master_df.loc[idx, 'Processing Status'] = 'ND'
            st.session_state.current_index += 1
            st.rerun()
else:
    st.info("Upload your Excel file in the sidebar to start.")
