import streamlit as st
import pandas as pd
import io

# --- INITIAL SETUP ---
st.set_page_config(layout="wide", page_title="DWR Well Log Transcriber")

# Initialize session state for data persistence
if 'master_df' not in st.session_state:
    st.session_state.master_df = None
if 'log_data' not in st.session_state:
    st.session_state.log_data = pd.DataFrame(columns=['Top Depth', 'Bottom Depth', 'Lithology'])
if 'output_df' not in st.session_state:
    st.session_state.output_df = pd.DataFrame(columns=['Receipt', 'Top Depth', 'Bottom Depth', 'Lithology'])
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0

# --- VALIDATION ENGINE ---
def validate_log(df):
    errors = []
    if df.empty:
        errors.append("The table is empty. Please enter data before submitting.")
        return errors
    if df.isnull().values.any() or (df == "").values.any():
        errors.append("Empty cells detected. Every row needs Top, Bottom, and Lithology.")
    
    for i in range(len(df)):
        try:
            top = float(df.iloc[i]['Top Depth'])
            bottom = float(df.iloc[i]['Bottom Depth'])
            if top >= bottom:
                errors.append(f"Row {i+1}: Top ({top}) must be less than Bottom ({bottom}).")
            if i < len(df) - 1:
                next_top = float(df.iloc[i+1]['Top Depth'])
                if bottom != next_top:
                    errors.append(f"Gap/Overlap at Row {i+1}: Bottom ({bottom}) doesn't match next Top ({next_top}).")
        except ValueError:
            errors.append(f"Row {i+1}: Depths must be numeric values.")
    return errors

# --- DIALOGS ---
@st.dialog("Confirm No Data")
def confirm_no_data(receipt):
    st.write(f"Are you sure you want to mark {receipt} as No Data (ND)?")
    if st.button("Confirm ND"):
        idx = st.session_state.master_df[st.session_state.master_df['Col_0'] == receipt].index
        st.session_state.master_df.loc[idx, 'Status'] = 'ND'
        st.session_state.current_index += 1
        st.success(f"Marked {receipt} as ND.")
        st.rerun()

@st.dialog("Confirm Submission")
def confirm_submit(receipt, notes, data):
    st.write(f"Is the log for {receipt} complete and verified?")
    if st.button("Yes, Submit Log"):
        # 1. Update Master
        idx = st.session_state.master_df[st.session_state.master_df['Col_0'] == receipt].index
        st.session_state.master_df.loc[idx, 'Status'] = 'Complete'
        st.session_state.master_df.loc[idx, 'Notes'] = notes
        
        # 2. Append to Output
        temp_output = data.copy()
        temp_output['Receipt'] = receipt
        st.session_state.output_df = pd.concat([st.session_state.output_df, temp_output], ignore_index=True)
        
        # 3. Reset for next well
        st.session_state.log_data = pd.DataFrame(columns=['Top Depth', 'Bottom Depth', 'Lithology'])
        st.session_state.current_index += 1
        st.success("Log successfully appended to output!")
        st.rerun()

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.title("⚙️ Project Controls")
    st.error("⚠️ DATA SAFETY: Download CSVs before closing the tab!")
    
    uploaded_file = st.file_uploader("1. Upload DWR Master Excel", type="xlsx")
    
    if st.session_state.master_df is not None:
        st.markdown("---")
        total = len(st.session_state.master_df)
        done = len(st.session_state.master_df[st.session_state.master_df['Status'] != 'Pending'])
        st.write(f"**Progress:** {done}/{total} Wells")
        st.progress(done / total)
        
        st.markdown("---")
        st.header("💾 2. Export Data")
        st.download_button("Download Master (Status)", st.session_state.master_df.to_csv(index=False), "master_tracking.csv")
        st.download_button("Download Output (Data)", st.session_state.output_df.to_csv(index=False), "well_lithology_data.csv")

# --- MAIN INTERFACE ---
st.title("🚰 DWR Well Log Transcriber")

main_tab, instr_tab = st.tabs(["🏗️ Workspace", "📖 Instructions & Best Practices"])

with instr_tab:
    st.header("Transcription Protocol")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🚀 Quick Start")
        st.markdown("""
        1. **Select Well:** Use the dropdown or search to find your Receipt.
        2. **Open Log:** Click the DWR link to open the PDF record.
        3. **Entry:** Enter Top depths. Hit **⚡ Auto-Fill** to link them to Bottom depths.
        4. **Submit:** Click 'Submit Log'. The app will validate your data for errors.
        """)
    with c2:
        st.subheader("🛡️ Best Practices")
        st.info("**Leading Zeroes:** The 'R' prefix protects your IDs from Excel's auto-formatting.")
        st.warning("**No Gaps:** Ensure the 'Bottom' of one layer matches the 'Top' of the next layer.")
        st.success("**Final Step:** Always download BOTH files at the end of your session.")
    st.subheader("🕵️ Quality Control Tip")
    st.markdown("""
    - **Handwriting & Scans:** If a driller's log is illegible, do not guess. 
    - **The Action:** Use the **No Data** button and add a Note: *"Scan quality too low to interpret"* or *"Handwriting unreadable."* - **The Why:** This ensures your future statistical models in R aren't trained on "guessed" data.
    """)
with main_tab:
    if uploaded_file:
        if st.session_state.master_df is None:
            raw_df = pd.read_excel(uploaded_file, header=None)
            raw_df.columns = [f"Col_{i}" for i in range(len(raw_df.columns))]
            raw_df['Col_0'] = 'R' + raw_df['Col_0'].astype(str)
            raw_df['Status'] = 'Pending'
            raw_df['Notes'] = ''
            st.session_state.master_df = raw_df

        # WELL SELECTION
        receipts = st.session_state.master_df['Col_0'].tolist()
        if st.session_state.current_index >= len(receipts):
            st.success("All wells processed!")
            st.session_state.current_index = len(receipts) - 1

        selected_receipt = st.selectbox("Select Well Receipt", receipts, index=st.session_state.current_index)
        st.session_state.current_index = receipts.index(selected_receipt)

        # LINK & INFO
        clean_receipt = selected_receipt.lstrip('R')
        dwr_url = f"https://dwr.state.co.us/Tools/WellPermits/{clean_receipt}"
        st.markdown(f"### 📄 [Open DWR Record for {clean_receipt}]({dwr_url})")
        
        well_info = st.session_state.master_df[st.session_state.master_df['Col_0'] == selected_receipt].iloc[0]
        notes = st.text_input("Transcription Notes", value=well_info['Notes'], placeholder="Enter specific observations...")

        # TABLE
        st.subheader("Lithology Log")
        if st.button("⚡ Auto-Fill Bottom Depths"):
            df = st.session_state.log_data
            if len(df) > 1:
                for i in range(len(df) - 1):
                    df.at[i, 'Bottom Depth'] = df.at[i+1, 'Top Depth']
                st.session_state.log_data = df

        edited_df = st.data_editor(st.session_state.log_data, num_rows="dynamic", use_container_width=True)
        st.session_state.log_data = edited_df

        # ACTIONS
        col1, col2, _ = st.columns([1, 1, 2])
        with col1:
            if st.button("Submit Log", type="primary", use_container_width=True):
                errors = validate_log(edited_df)
                if errors:
                    for e in errors: st.error(e)
                else:
                    confirm_submit(selected_receipt, notes, edited_df)
        with col2:
            if st.button("No Data", use_container_width=True):
                confirm_no_data(selected_receipt)

        # PREVIEW
        st.markdown("---")
        st.subheader("🔍 Session Preview")
        if not st.session_state.output_df.empty:
            st.dataframe(st.session_state.output_df.tail(5).iloc[::-1], use_container_width=True)
        else:
            st.caption("Submit a log to see a preview here.")
    else:
        st.info("👈 Please upload the DWR Excel file in the sidebar to begin.")
