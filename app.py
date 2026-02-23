import streamlit as st
import pandas as pd
import io

# --- INITIAL SETUP ---
st.set_page_config(layout="wide", page_title="DWR Well Log Transcriber")

# Initialize session state
if 'master_df' not in st.session_state:
    st.session_state.master_df = None
if 'log_data' not in st.session_state:
    st.session_state.log_data = pd.DataFrame([{"Top Depth": None, "Bottom Depth": None, "Lithology": ""}] * 10)
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

# --- VALIDATION ENGINE ---
def get_validation_status(df):
    """Checks each row and returns a list of status icons/messages."""
    status = ["✅"] * len(df)
    errors = []
    
    for i in range(len(df)):
        row = df.iloc[i]
        try:
            # Skip empty rows for icon logic
            if pd.isna(row['Top Depth']) and pd.isna(row['Bottom Depth']):
                status[i] = "⚪"
                continue
                
            t, b = float(row['Top Depth']), float(row['Bottom Depth'])
            
            # Logic Check
            if t >= b:
                status[i] = "❌ Logic Error"
                errors.append(f"Row {i+1}: Top must be less than Bottom.")
            
            # Gap Check
            if i < len(df) - 1:
                next_val = df.iloc[i+1]['Top Depth']
                if not pd.isna(next_val):
                    if b != float(next_val):
                        status[i] = "⚠️ Gap Below"
                        errors.append(f"Gap between Row {i+1} and {i+2} ({b} vs {next_val})")
        except:
            status[i] = "❓ Non-Numeric"
            errors.append(f"Row {i+1}: Invalid depth entry.")
            
    return status, errors

# --- DIALOGS ---
@st.dialog("Confirm No Data")
def confirm_no_data(receipt):
    st.write(f"Mark {receipt} as No Data (ND)?")
    if st.button("Confirm ND"):
        idx = st.session_state.master_df[st.session_state.master_df['Receipt'] == receipt].index
        st.session_state.master_df.loc[idx, 'Processing Status'] = 'ND'
        st.session_state.current_index += 1
        st.rerun()

@st.dialog("Confirm Submission")
def confirm_submit(receipt, notes, data):
    st.write(f"Save log for {receipt}? (Empty rows will be preserved)")
    if st.button("Yes, Submit Log"):
        idx = st.session_state.master_df[st.session_state.master_df['Receipt'] == receipt].index
        st.session_state.master_df.loc[idx, 'Processing Status'] = 'Complete'
        st.session_state.master_df.loc[idx, 'Notes'] = notes
        temp_output = data.copy()
        temp_output['Receipt'] = receipt
        st.session_state.output_df = pd.concat([st.session_state.output_df, temp_output], ignore_index=True)
        st.session_state.log_data = pd.DataFrame([{"Top Depth": None, "Bottom Depth": None, "Lithology": ""}] * 10)
        st.session_state.current_index += 1
        st.rerun()

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚙️ Controls")
    uploaded_file = st.file_uploader("Upload DWR Master Excel", type="xlsx")
    if st.session_state.master_df is not None:
        st.markdown("---")
        total, done = len(st.session_state.master_df), len(st.session_state.master_df[st.session_state.master_df['Processing Status'] != 'Pending'])
        st.write(f"**Progress:** {done}/{total}")
        st.progress(done / total)
        st.download_button("Download Master", st.session_state.master_df.to_csv(index=False), "master_tracking.csv")
        st.download_button("Download Output", st.session_state.output_df.to_csv(index=False), "well_lithology_data.csv")

# --- MAIN APP ---
main_tab, instr_tab = st.tabs(["🏗️ Workspace", "📖 Instructions"])

with instr_tab:
    st.header("Logging Protocol")
    st.markdown("""
    - **⚪ White Circle:** Row is empty.
    - **✅ Green Check:** Row looks good.
    - **⚠️ Yellow Warning:** Depth gap between this row and the next.
    - **❌ Red X:** Top depth is greater than or equal to Bottom depth.
    - **🕵️ Data Quality:** If the log is unreadable, use 'No Data' and note why.
    """)

with main_tab:
    if uploaded_file:
        if st.session_state.master_df is None:
            st.session_state.master_df = process_master(pd.read_excel(uploaded_file, header=None))

        receipts = st.session_state.master_df['Receipt'].tolist()
        if st.session_state.current_index >= len(receipts):
            st.success("All wells processed!")
            st.session_state.current_index = len(receipts) - 1

        selected_receipt = st.selectbox("Current Well", receipts, index=st.session_state.current_index)
        st.session_state.current_index = receipts.index(selected_receipt)

        # DWR LINK
        clean_receipt = selected_receipt.lstrip('R')
        st.markdown(f"## 📄 [Open DWR Record {clean_receipt}](https://dwr.state.co.us/Tools/WellPermits/{clean_receipt})")
        
        well_info = st.session_state.master_df[st.session_state.master_df['Receipt'] == selected_receipt].iloc[0]
        notes = st.text_input("Notes", value=well_info['Notes'])

        # TABLE & AUTOFILL
        st.subheader("Lithology Entry")
        if st.button("⚡ Auto-Fill Bottom Depths"):
            df_t = st.session_state.log_data.copy()
            for i in range(len(df_t)-1):
                if not pd.isna(df_t.at[i+1, 'Top Depth']):
                    df_t.at[i, 'Bottom Depth'] = df_t.at[i+1, 'Top Depth']
            st.session_state.log_data = df_t
            st.rerun()

        # Add a temporary status column for visual feedback
        display_df = st.session_state.log_data.copy()
        status_icons, error_list = get_validation_status(display_df)
        display_df.insert(0, "Status", status_icons)

        edited_df = st.data_editor(
            display_df, 
            num_rows="dynamic", 
            use_container_width=True, 
            hide_index=True,
            key="editor_v2"
        )
        # Update session state (excluding the temporary Status column)
        st.session_state.log_data = edited_df.drop(columns=["Status"])

        # SUBMIT
        c1, c2, _ = st.columns([1, 1, 2])
        with c1:
            if st.button("Submit Log", type="primary", use_container_width=True):
                _, final_errors = get_validation_status(st.session_state.log_data)
                if final_errors:
                    for e in final_errors: st.error(e)
                else:
                    confirm_submit(selected_receipt, notes, st.session_state.log_data)
        with col2:
            if st.button("No Data", use_container_width=True):
                confirm_no_data(selected_receipt)
    else:
        st.info("Please upload the DWR Excel file in the sidebar.")
