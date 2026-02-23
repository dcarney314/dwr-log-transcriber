import streamlit as st
import pandas as pd

# --- INITIAL SETUP ---
st.set_page_config(layout="wide", page_title="DWR Well Log Transcriber")

# Standard session state setup
if 'master_df' not in st.session_state:
    st.session_state.master_df = None
if 'output_df' not in st.session_state:
    st.session_state.output_df = pd.DataFrame(columns=['Receipt', 'Top Depth', 'Bottom Depth', 'Lithology'])
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
if 'current_table_df' not in st.session_state:
    # 20 rows is standard, but you can change this
    st.session_state.current_table_df = pd.DataFrame([{"Top Depth": None, "Bottom Depth": None, "Lithology": ""}] * 20)

# --- THE FIX: MANUAL TABLE UPDATE ---
def update_table():
    # This grabs the data from the editor's internal state only when we need it
    if "main_editor" in st.session_state:
        # We merge the changes into our stable dataframe
        new_data = st.session_state["main_editor"]["edited_rows"]
        for row_idx, changes in new_data.items():
            for key, val in changes.items():
                st.session_state.current_table_df.at[int(row_idx), key] = val

# --- MAIN APP ---
if st.session_state.master_df is not None:
    receipts = st.session_state.master_df['Receipt'].tolist()
    selected_receipt = st.selectbox("Current Well", receipts, index=st.session_state.current_index)
    st.session_state.current_index = receipts.index(selected_receipt)

    # DWR Link & Notes
    clean_receipt = selected_receipt.lstrip('R')
    st.markdown(f"## 📄 [Open DWR Record {clean_receipt}](https://dwr.state.co.us/Tools/WellPermits/{clean_receipt})")
    
    well_idx = st.session_state.master_df[st.session_state.master_df['Receipt'] == selected_receipt].index[0]
    notes = st.text_input("Notes", value=st.session_state.master_df.at[well_idx, 'Notes'])

    st.subheader("Lithology Entry")

    # --- THE FORM WRAPPER ---
    with st.form("entry_form", clear_on_submit=False):
        # The table now lives inside a form. It will NOT refresh until a button is clicked.
        edited_df = st.data_editor(
            st.session_state.current_table_df,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="main_editor"
        )
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            # We use a special button that "submits" the form
            submit_pressed = st.form_submit_button("✅ Verify & Submit Log", type="primary", use_container_width=True)
        with col_f2:
            autofill_pressed = st.form_submit_button("⚡ Auto-Fill Bottoms", use_container_width=True)

    # --- LOGIC AFTER FORM SUBMISSION ---
    if autofill_pressed:
        # 1. Update our state from the editor first
        st.session_state.current_table_df = edited_df
        # 2. Run the autofill
        df_work = st.session_state.current_table_df.copy()
        for i in range(len(df_work) - 1):
            next_t = df_work.at[i+1, 'Top Depth']
            if pd.notnull(next_t) and next_t != "":
                df_work.at[i, 'Bottom Depth'] = next_t
        st.session_state.current_table_df = df_work
        st.rerun()

    if submit_pressed:
        # 1. Capture the data
        st.session_state.current_table_df = edited_df
        # 2. Run your validation (gap checks, logic checks)
        # (Insert your validation function here)
        
        # 3. If valid, save to output and clear
        ready_data = st.session_state.current_table_df.dropna(how='all').copy()
        ready_data['Receipt'] = selected_receipt
        st.session_state.output_df = pd.concat([st.session_state.output_df, ready_data], ignore_index=True)
        
        # Reset and Move Next
        st.session_state.current_table_df = pd.DataFrame([{"Top Depth": None, "Bottom Depth": None, "Lithology": ""}] * 20)
        st.session_state.current_index += 1
        st.success("Log Saved!")
        st.rerun()

    if st.button("No Data"):
        st.session_state.master_df.at[well_idx, 'Processing Status'] = 'ND'
        st.session_state.current_index += 1
        st.session_state.current_table_df = pd.DataFrame([{"Top Depth": None, "Bottom Depth": None, "Lithology": ""}] * 20)
        st.rerun()
