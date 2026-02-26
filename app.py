import streamlit as st
import pandas as pd

# --- INITIAL SETUP ---
st.set_page_config(layout="wide", page_title="DWR Well Log Transcriber")

EMPTY_TABLE = lambda: pd.DataFrame(
    [{"Top Depth": None, "Bottom Depth": None, "Lithology": ""}] * 20
)

if 'master_df' not in st.session_state:
    st.session_state.master_df = None
if 'output_df' not in st.session_state:
    st.session_state.output_df = pd.DataFrame(columns=['Receipt', 'Top Depth', 'Bottom Depth', 'Lithology'])
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
if 'current_table_df' not in st.session_state:
    st.session_state.current_table_df = EMPTY_TABLE()
if 'editor_key' not in st.session_state:
    # Incrementing this key forces the editor to fully re-mount (used on submit/reset)
    st.session_state.editor_key = 0


def _apply_editor_state():
    """
    Read the raw widget state from the data_editor and merge any edits
    into current_table_df. Called at the TOP of every render so that
    Enter-key reruns never discard work.
    """
    key = f"main_editor_{st.session_state.editor_key}"
    if key not in st.session_state:
        return
    widget_state = st.session_state[key]

    # Apply edited rows
    for row_idx_str, changes in widget_state.get("edited_rows", {}).items():
        row_idx = int(row_idx_str)
        for col, val in changes.items():
            st.session_state.current_table_df.at[row_idx, col] = val

    # Apply added rows
    for new_row in widget_state.get("added_rows", []):
        st.session_state.current_table_df = pd.concat(
            [st.session_state.current_table_df, pd.DataFrame([new_row])],
            ignore_index=True
        )

    # Apply deleted rows
    deleted = widget_state.get("deleted_rows", [])
    if deleted:
        st.session_state.current_table_df = (
            st.session_state.current_table_df
            .drop(index=deleted)
            .reset_index(drop=True)
        )


# --- SYNC EDITOR STATE ON EVERY RUN (the critical fix) ---
_apply_editor_state()


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

    # Unique key per editor "session" — incrementing it on reset forces a clean mount
    editor_key = f"main_editor_{st.session_state.editor_key}"

    with st.form("entry_form", clear_on_submit=False):
        st.data_editor(
            st.session_state.current_table_df,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key=editor_key,
            column_config={
                "Top Depth": st.column_config.NumberColumn("Top Depth", min_value=0),
                "Bottom Depth": st.column_config.NumberColumn("Bottom Depth", min_value=0),
                "Lithology": st.column_config.TextColumn("Lithology"),
            }
        )

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            submit_pressed = st.form_submit_button("✅ Verify & Submit Log", type="primary", use_container_width=True)
        with col_f2:
            autofill_pressed = st.form_submit_button("⚡ Auto-Fill Bottoms", use_container_width=True)

    # --- BUTTON LOGIC ---
    # Note: _apply_editor_state() already ran at the top of this rerun,
    # so current_table_df is always up-to-date here.

    if autofill_pressed:
        df_work = st.session_state.current_table_df.copy()
        for i in range(len(df_work) - 1):
            next_t = df_work.at[i + 1, 'Top Depth']
            if pd.notnull(next_t) and next_t != "":
                df_work.at[i, 'Bottom Depth'] = next_t
        st.session_state.current_table_df = df_work
        # Bump the key so the editor re-mounts with the new autofilled data
        st.session_state.editor_key += 1
        st.rerun()

    if submit_pressed:
        # --- Validation ---
        df_check = st.session_state.current_table_df.dropna(subset=['Top Depth', 'Bottom Depth', 'Lithology'], how='all')
        errors = []
        for i, row in df_check.iterrows():
            if pd.isnull(row['Top Depth']) or pd.isnull(row['Bottom Depth']):
                errors.append(f"Row {i+1}: missing Top or Bottom Depth.")
            elif row['Top Depth'] >= row['Bottom Depth']:
                errors.append(f"Row {i+1}: Top Depth must be less than Bottom Depth.")
        # Check for gaps/overlaps between consecutive rows
        valid_rows = df_check.dropna(subset=['Top Depth', 'Bottom Depth']).reset_index(drop=True)
        for i in range(len(valid_rows) - 1):
            this_bot = valid_rows.at[i, 'Bottom Depth']
            next_top = valid_rows.at[i + 1, 'Top Depth']
            if this_bot != next_top:
                errors.append(f"Gap or overlap between rows {i+1} and {i+2} ({this_bot} → {next_top}).")

        if errors:
            for e in errors:
                st.error(e)
        else:
            ready_data = df_check.copy()
            ready_data['Receipt'] = selected_receipt
            st.session_state.output_df = pd.concat(
                [st.session_state.output_df, ready_data], ignore_index=True
            )
            # Reset table and advance
            st.session_state.current_table_df = EMPTY_TABLE()
            st.session_state.editor_key += 1
            st.session_state.current_index += 1
            st.success("Log Saved!")
            st.rerun()

    if st.button("No Data"):
        st.session_state.master_df.at[well_idx, 'Processing Status'] = 'ND'
        st.session_state.current_index += 1
        st.session_state.current_table_df = EMPTY_TABLE()
        st.session_state.editor_key += 1
        st.rerun()

    # --- Output Preview ---
    if not st.session_state.output_df.empty:
        with st.expander("📊 Output Preview", expanded=False):
            st.dataframe(st.session_state.output_df, use_container_width=True)

else:
    st.info("Upload a master spreadsheet to begin. Your file should contain a 'Receipt' column.")
    uploaded = st.file_uploader("Upload Master File (.xlsx or .csv)", type=["xlsx", "csv"])
    if uploaded:
        if uploaded.name.endswith(".csv"):
            st.session_state.master_df = pd.read_csv(uploaded, dtype=str)
        else:
            st.session_state.master_df = pd.read_excel(uploaded, dtype=str)
        # Ensure required columns exist
        for col in ['Receipt', 'Notes', 'Processing Status']:
            if col not in st.session_state.master_df.columns:
                st.session_state.master_df[col] = ""
        st.rerun()
