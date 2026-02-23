import streamlit as st
import pandas as pd

# --- INITIAL SETUP ---
st.set_page_config(layout="wide", page_title="DWR Well Log Transcriber")

# Initialize Master and Output 
if 'master_df' not in st.session_state:
    st.session_state.master_df = None
if 'output_df' not in st.session_state:
    st.session_state.output_df = pd.DataFrame(columns=['Receipt', 'Top Depth', 'Bottom Depth', 'Lithology'])
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
if 'current_table_df' not in st.session_state:
    st.session_state.current_table_df = pd.DataFrame([{"Top Depth": None, "Bottom Depth": None, "Lithology": ""}] * 20)

# --- DATA PROCESSING ---
def process_master(df):
    target_indices = [0, 1, 2, 22, 23, 24, 25]
    df = df.iloc[:, target_indices].copy()
    df.columns = ['Receipt', 'Permit Number', 'Permit Status', 'UTM X', 'UTM Y', 'Latitude', 'Longitude']
    df['Receipt'] = 'R' + df['Receipt'].astype(str)
    df['Processing Status'] = 'Pending'
    df['Notes'] = ''
    return df

# --- STRICT VALIDATION ---
def validate_log(df):
    errors = []
    # Identify rows that have at least one depth or lithology entry
    # We use this to ignore the "empty" rows at the bottom of your 20-row template
    active_rows = df.dropna(how='all').copy()
    
    if active_rows.empty:
        errors.append("The table is empty. Please enter data.")
        return errors, None

    for i in range(len(active_rows)):
        row = active_rows.iloc[i]
        try:
            # Check for missing values in active rows
            if pd.isnull(row['Top Depth']) or pd.isnull(row['Bottom Depth']):
                errors.append(f"Row {i+1} is missing a depth value.")
                continue
            
            t, b = float(row['Top Depth']), float(row['Bottom Depth'])
            
            if t >= b:
                errors.append(f"Row {i+1}: Top ({t}) must be less than Bottom ({b}).")
            
            # Continuity Check
            if i < len(active_rows) - 1:
                next_row = active_rows.iloc[i+1]
                if pd.notnull(next_row['Top Depth']):
                    next_t = float(next_row['Top Depth'])
                    if b != next_t:
                        errors.append(f"Gap/Overlap: Row {i+1} ends at {b}, but Row {i+2} starts at {next_t}.")
        except ValueError:
            errors.append(f"Row {i+1} contains non-numeric depth values.")
            
    return errors, active_rows

# --- MAIN INTERFACE ---
with st.sidebar:
    st.title("⚙️ Controls")
    uploaded_file = st.file_uploader("Upload DWR Excel", type="xlsx")
    if st.session_state.master_df is not None:
        st.download_button("Download Master", st.session_state.master_df.to_csv(index=False), "master_tracking.csv")
        st.download_button("Download Output", st.session_state.output_df.to_csv(index=False), "well_lithology_data.csv")

if uploaded_file:
    if st.session_state.master_df is None:
        st.session_state.master_df = process_master(pd.read_excel(uploaded_file, header=None))

    receipts = st.session_state.master_df['Receipt'].tolist()
    selected_receipt = st.selectbox("Current Well", receipts, index=st.session_state.current_index)
    st.session_state.current_index = receipts.index(selected_receipt)

    # Link & Notes
    clean_receipt = selected_receipt.lstrip('R')
    st.markdown(f"## 📄 [Open DWR Record {clean_receipt}](https://dwr.state.co.us/Tools/WellPermits/{clean_receipt})")
    
    well_idx = st.session_state.master_df[st.session_state.master_df['Receipt'] == selected_receipt].index[0]
    notes = st.text_input("Notes", value=st.session_state.master_df.at[well_idx, 'Notes'])

    # --- THE TABLE ---
    st.subheader("Lithology Entry")
    
    if st.button("⚡ Auto-Fill Bottom Depths"):
        df_work = st.session_state.current_table_df.copy()
        for i in range(len(df_work) - 1):
            next_t = df_work.at[i+1, 'Top Depth']
            if pd.notnull(next_t) and next_t != "":
                df_work.at[i, 'Bottom Depth'] = next_t
        st.session_state.current_table_df = df_work
        st.rerun()

    edited_df = st.data_editor(
        st.session_state.current_table_df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="main_editor"
    )
    st.session_state.current_table_df = edited_df

    # --- SUBMISSION ---
    c1, c2, _ = st.columns([1, 1, 2])
    with c1:
        if st.button("Submit Log", type="primary", use_container_width=True):
            # 1. Run Validation
            err_list, ready_data = validate_log(st.session_state.current_table_df)
            
            if err_list:
                # 2. Block Saving and Show Notifications
                st.error("🛑 Log has problems! Fix the following before saving:")
                for e in err_list:
                    st.warning(e)
            else:
                # 3. Save ONLY if 0 errors found
                st.session_state.master_df.at[well_idx, 'Processing Status'] = 'Complete'
                st.session_state.master_df.at[well_idx, 'Notes'] = notes
                
                ready_data['Receipt'] = selected_receipt
                st.session_state.output_df = pd.concat([st.session_state.output_df, ready_data], ignore_index=True)
                
                # Reset
                st.session_state.current_table_df = pd.DataFrame([{"Top Depth": None, "Bottom Depth": None, "Lithology": ""}] * 20)
                st.session_state.current_index += 1
                st.success("✅ Log Verified and Saved!")
                st.rerun()
                
    with c2:
        if st.button("No Data", use_container_width=True):
            st.session_state.master_df.at[well_idx, 'Processing Status'] = 'ND'
            st.session_state.current_index += 1
            st.session_state.current_table_df = pd.DataFrame([{"Top Depth": None, "Bottom Depth": None, "Lithology": ""}] * 20)
            st.rerun()
else:
    st.info("Upload your Excel file in the sidebar to start.")
