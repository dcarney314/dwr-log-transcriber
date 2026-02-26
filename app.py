import streamlit as st
import pandas as pd
import io

# --- INITIAL SETUP ---
st.set_page_config(layout="wide", page_title="DWR Well Log Transcriber")

EMPTY_TABLE = lambda: pd.DataFrame(
    [{"Top Depth": None, "Bottom Depth": None, "Lithology": ""}] * 20
)

# Column index constants (0-based) for the master input file
COL_RECEIPT       = 0   # Column 1
COL_PERMIT        = 1   # Column 2
COL_PERMIT_STATUS = 2   # Column 3
COL_UTM_X         = 22  # Column 23
COL_UTM_Y         = 23  # Column 24
COL_LAT           = 24  # Column 25
COL_LON           = 25  # Column 26

if 'master_df' not in st.session_state:
    st.session_state.master_df = None
if 'log_output_df' not in st.session_state:
    st.session_state.log_output_df = pd.DataFrame(
        columns=['Receipt', 'Top Depth', 'Bottom Depth', 'Lithology']
    )
if 'master_output_df' not in st.session_state:
    st.session_state.master_output_df = pd.DataFrame(
        columns=['Receipt', 'Permit Number', 'UTM X', 'UTM Y',
                 'Latitude', 'Longitude', 'Notes', 'Processing Status']
    )
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
if 'current_table_df' not in st.session_state:
    st.session_state.current_table_df = EMPTY_TABLE()
if 'editor_key' not in st.session_state:
    st.session_state.editor_key = 0

# Undo stack — each entry is a dict with keys:
#   'current_index', 'log_rows', 'master_row', 'table_df', 'notes', 'status'
if 'undo_stack' not in st.session_state:
    st.session_state.undo_stack = []


# ---- HELPERS ----

def _apply_editor_state():
    """Merge pending data_editor widget changes into current_table_df on every rerun."""
    key = f"main_editor_{st.session_state.editor_key}"
    if key not in st.session_state:
        return
    widget_state = st.session_state[key]

    for row_idx_str, changes in widget_state.get("edited_rows", {}).items():
        row_idx = int(row_idx_str)
        for col, val in changes.items():
            if row_idx < len(st.session_state.current_table_df):
                st.session_state.current_table_df.at[row_idx, col] = val

    for new_row in widget_state.get("added_rows", []):
        st.session_state.current_table_df = pd.concat(
            [st.session_state.current_table_df, pd.DataFrame([new_row])],
            ignore_index=True
        )

    deleted = widget_state.get("deleted_rows", [])
    if deleted:
        st.session_state.current_table_df = (
            st.session_state.current_table_df
            .drop(index=deleted)
            .reset_index(drop=True)
        )


def safe_get_col(row, col_idx):
    try:
        return row.iloc[col_idx]
    except IndexError:
        return ""


def add_prefix(value, prefix):
    s = str(value).strip()
    if not s or s.lower() == 'nan':
        return ""
    if not s.startswith(prefix):
        return prefix + s
    return s


def reset_table():
    st.session_state.current_table_df = EMPTY_TABLE()
    st.session_state.editor_key += 1


def to_csv_bytes(df):
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def is_row_empty(row):
    """True if a table row has no meaningful data in any field."""
    return (
        (pd.isnull(row['Top Depth'])    or str(row['Top Depth']).strip()    == "") and
        (pd.isnull(row['Bottom Depth']) or str(row['Bottom Depth']).strip() == "") and
        (pd.isnull(row['Lithology'])    or str(row['Lithology']).strip()    == "")
    )


def validate_and_trim(table_df):
    """
    1. Strip trailing all-empty rows.
    2. Validate the remaining rows.
    Returns (trimmed_df, errors_list).
    Errors are raised for interior empty rows, depth inversions, and gaps/overlaps.
    Empty trailing rows are silently dropped.
    """
    df = table_df.copy().reset_index(drop=True)

    # Drop trailing empty rows
    last_data_idx = -1
    for i in range(len(df) - 1, -1, -1):
        if not is_row_empty(df.iloc[i]):
            last_data_idx = i
            break

    if last_data_idx == -1:
        return pd.DataFrame(columns=df.columns), ["No data entered — please fill in at least one row."]

    df = df.iloc[:last_data_idx + 1].reset_index(drop=True)

    errors = []

    for i, row in df.iterrows():
        if is_row_empty(row):
            errors.append(f"Row {i+1}: empty row in the middle of the log — please fill or remove it.")
            continue
        top_missing = pd.isnull(row['Top Depth'])    or str(row['Top Depth']).strip()    == ""
        bot_missing = pd.isnull(row['Bottom Depth']) or str(row['Bottom Depth']).strip() == ""
        if top_missing:
            errors.append(f"Row {i+1}: missing Top Depth.")
        if bot_missing:
            errors.append(f"Row {i+1}: missing Bottom Depth.")
        if not top_missing and not bot_missing:
            if float(row['Top Depth']) >= float(row['Bottom Depth']):
                errors.append(f"Row {i+1}: Top Depth ({row['Top Depth']}) must be less than Bottom Depth ({row['Bottom Depth']}).")

    # Gap / overlap check on consecutive valid rows
    valid = df.dropna(subset=['Top Depth', 'Bottom Depth']).reset_index(drop=True)
    for i in range(len(valid) - 1):
        this_bot = float(valid.at[i,   'Bottom Depth'])
        next_top = float(valid.at[i+1, 'Top Depth'])
        if this_bot != next_top:
            errors.append(
                f"Gap or overlap between rows {i+1} and {i+2} "
                f"({this_bot} → {next_top})."
            )

    return df, errors


# --- SYNC EDITOR STATE ON EVERY RUN ---
_apply_editor_state()


# =========================================================
# UPLOAD SCREEN
# =========================================================
if st.session_state.master_df is None:
    st.title("🚰 DWR Well Log Transcriber")

    st.markdown("### 📥 Import Colorado DWR Data")
    st.markdown(
        """
1. **Go to the DWR Well Permit Search:** [dwr.state.co.us/Tools/WellPermits](https://dwr.state.co.us/Tools/WellPermits)
2. **Filter wells** by region, permit status, latitude/longitude, or other attributes as needed.
3. **Select all and copy** the entire well attribute table from the results page.
4. **Paste into a blank Excel workbook** (.xlsx) — no header row, data starting in cell A1.
5. **Save the file**, then upload it below.
        """
    )

    st.info(
        "**Expected column layout:** Receipt (col 1) · Permit Number (col 2) · "
        "Permit Status (col 3) · UTM X (col 23) · UTM Y (col 24) · "
        "Latitude (col 25) · Longitude (col 26). "
        "No header row should be present in the file."
    )

    uploaded = st.file_uploader("Upload Master File (.xlsx or .csv)", type=["xlsx", "csv"])
    if uploaded:
        if uploaded.name.endswith(".csv"):
            df_raw = pd.read_csv(uploaded, dtype=str, header=None)
        else:
            df_raw = pd.read_excel(uploaded, dtype=str, header=None)

        df_raw.fillna("", inplace=True)

        if 'Notes' not in df_raw.columns:
            df_raw['Notes'] = ""
        if 'Processing Status' not in df_raw.columns:
            df_raw['Processing Status'] = ""

        st.session_state.master_df = df_raw
        st.rerun()

# =========================================================
# MAIN APP
# =========================================================
else:
    df = st.session_state.master_df

    raw_receipts     = [str(df.iloc[i, COL_RECEIPT]).strip() for i in range(len(df))]
    display_receipts = [add_prefix(r, "R") for r in raw_receipts]

    idx = min(st.session_state.current_index, len(display_receipts) - 1)
    st.session_state.current_index = idx

    # --- Sidebar ---
    with st.sidebar:
        st.header("Progress")
        total  = len(display_receipts)
        logged = len(st.session_state.master_output_df)
        st.metric("Wells Processed", f"{logged} / {total}")
        st.progress(logged / total if total > 0 else 0)

        st.divider()
        st.header("Export Outputs")
        st.download_button(
            label="⬇️ Download Log Output",
            data=to_csv_bytes(st.session_state.log_output_df),
            file_name="log_output.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=st.session_state.log_output_df.empty,
        )
        st.download_button(
            label="⬇️ Download Master Output",
            data=to_csv_bytes(st.session_state.master_output_df),
            file_name="master_output.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=st.session_state.master_output_df.empty,
        )

        st.divider()
        if st.button("🔄 Load New Master File", use_container_width=True):
            for key in ['master_df', 'log_output_df', 'master_output_df',
                        'current_index', 'current_table_df', 'editor_key', 'undo_stack']:
                del st.session_state[key]
            st.rerun()

    # --- Well Selector ---
    selected_display = st.selectbox("Current Well", display_receipts, index=idx)
    st.session_state.current_index = display_receipts.index(selected_display)

    well_row     = df.iloc[st.session_state.current_index]
    raw_receipt  = raw_receipts[st.session_state.current_index]
    disp_receipt = display_receipts[st.session_state.current_index]
    master_idx   = df.index[st.session_state.current_index]

    st.markdown(
        f"## 📄 [Open DWR Record {disp_receipt}]"
        f"(https://dwr.state.co.us/Tools/WellPermits/{raw_receipt})"
    )

    permit_raw    = safe_get_col(well_row, COL_PERMIT)
    permit_status = safe_get_col(well_row, COL_PERMIT_STATUS)
    st.caption(f"Permit: {add_prefix(permit_raw, 'P')}  |  Status: {permit_status}")

    notes_val = df.at[master_idx, 'Notes']
    notes     = st.text_input("Notes", value=notes_val,
                              key=f"notes_{st.session_state.current_index}")

    # --- No Data (above lithology table) ---
    col_nd, col_undo = st.columns([1, 1])
    with col_nd:
        no_data_pressed = st.button("⛔ No Data", use_container_width=True)
    with col_undo:
        undo_pressed = st.button(
            "↩️ Undo Last Entry",
            use_container_width=True,
            disabled=len(st.session_state.undo_stack) == 0,
        )

    st.subheader("Lithology Entry")

    editor_key = f"main_editor_{st.session_state.editor_key}"

    with st.form("entry_form", clear_on_submit=False):
        # Top action row
        top_c1, top_c2, top_c3 = st.columns([2, 2, 3])
        with top_c1:
            submit_pressed_top   = st.form_submit_button("✅ Verify & Submit Log",
                                                         type="primary", use_container_width=True)
        with top_c2:
            autofill_pressed_top = st.form_submit_button("⚡ Auto-Fill Bottom Depths ",
                                                         use_container_width=True)

        st.data_editor(
            st.session_state.current_table_df,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key=editor_key,
            column_config={
                "Top Depth":    st.column_config.NumberColumn("Top Depth",    min_value=0),
                "Bottom Depth": st.column_config.NumberColumn("Bottom Depth", min_value=0),
                "Lithology":    st.column_config.TextColumn("Lithology"),
            },
        )

        # Bottom action row
        bot_c1, bot_c2, bot_c3 = st.columns([2, 2, 3])
        with bot_c1:
            submit_pressed_bot   = st.form_submit_button("✅ Verify & Submit Log ",
                                                         type="primary", use_container_width=True)
        with bot_c2:
            autofill_pressed_bot = st.form_submit_button("⚡ Auto-Fill Bottom Depths",
                                                         use_container_width=True)

    submit_pressed   = submit_pressed_top   or submit_pressed_bot
    autofill_pressed = autofill_pressed_top or autofill_pressed_bot

    # --- Auto-Fill ---
    if autofill_pressed:
        df_work = st.session_state.current_table_df.copy()
        for i in range(len(df_work) - 1):
            next_t = df_work.at[i + 1, 'Top Depth']
            if pd.notnull(next_t) and next_t != "":
                df_work.at[i, 'Bottom Depth'] = next_t
        st.session_state.current_table_df = df_work
        st.session_state.editor_key += 1
        st.rerun()

    # --- Submit ---
    if submit_pressed:
        trimmed_df, errors = validate_and_trim(st.session_state.current_table_df)

        if errors:
            for e in errors:
                st.error(e)
        else:
            # Save undo snapshot BEFORE committing
            st.session_state.undo_stack.append({
                'prev_index':    st.session_state.current_index,
                'table_df':      trimmed_df.copy(),
                'notes':         notes,
                'status':        'Logged',
                'log_rows_n':    len(trimmed_df),
                'master_rows_n': 1,
            })

            st.session_state.master_df.at[master_idx, 'Notes']             = notes
            st.session_state.master_df.at[master_idx, 'Processing Status'] = 'Logged'

            log_rows            = trimmed_df.copy()
            log_rows['Receipt'] = disp_receipt
            log_rows            = log_rows[['Receipt', 'Top Depth', 'Bottom Depth', 'Lithology']]
            st.session_state.log_output_df = pd.concat(
                [st.session_state.log_output_df, log_rows], ignore_index=True
            )

            new_master_row = pd.DataFrame([{
                'Receipt':           disp_receipt,
                'Permit Number':     add_prefix(safe_get_col(well_row, COL_PERMIT), "P"),
                'UTM X':             safe_get_col(well_row, COL_UTM_X),
                'UTM Y':             safe_get_col(well_row, COL_UTM_Y),
                'Latitude':          safe_get_col(well_row, COL_LAT),
                'Longitude':         safe_get_col(well_row, COL_LON),
                'Notes':             notes,
                'Processing Status': 'Logged',
            }])
            st.session_state.master_output_df = pd.concat(
                [st.session_state.master_output_df, new_master_row], ignore_index=True
            )

            reset_table()
            st.session_state.current_index += 1
            st.success("Log saved! Moving to next well.")
            st.rerun()

    # --- No Data ---
    if no_data_pressed:
        # Save undo snapshot
        st.session_state.undo_stack.append({
            'prev_index':    st.session_state.current_index,
            'table_df':      st.session_state.current_table_df.copy(),
            'notes':         notes,
            'status':        'ND',
            'log_rows_n':    0,
            'master_rows_n': 1,
        })

        st.session_state.master_df.at[master_idx, 'Notes']             = notes
        st.session_state.master_df.at[master_idx, 'Processing Status'] = 'ND'

        new_master_row = pd.DataFrame([{
            'Receipt':           disp_receipt,
            'Permit Number':     add_prefix(safe_get_col(well_row, COL_PERMIT), "P"),
            'UTM X':             safe_get_col(well_row, COL_UTM_X),
            'UTM Y':             safe_get_col(well_row, COL_UTM_Y),
            'Latitude':          safe_get_col(well_row, COL_LAT),
            'Longitude':         safe_get_col(well_row, COL_LON),
            'Notes':             notes,
            'Processing Status': 'ND',
        }])
        st.session_state.master_output_df = pd.concat(
            [st.session_state.master_output_df, new_master_row], ignore_index=True
        )

        reset_table()
        st.session_state.current_index += 1
        st.rerun()

    # --- Undo ---
    if undo_pressed and st.session_state.undo_stack:
        snap = st.session_state.undo_stack.pop()

        # Restore index
        st.session_state.current_index = snap['prev_index']

        # Restore the table so the user can re-edit
        st.session_state.current_table_df = snap['table_df'].copy()
        st.session_state.editor_key += 1

        # Roll back master_output_df (remove last N master rows)
        n_master = snap['master_rows_n']
        if n_master > 0 and len(st.session_state.master_output_df) >= n_master:
            st.session_state.master_output_df = st.session_state.master_output_df.iloc[:-n_master].reset_index(drop=True)

        # Roll back log_output_df (remove last N log rows)
        n_log = snap['log_rows_n']
        if n_log > 0 and len(st.session_state.log_output_df) >= n_log:
            st.session_state.log_output_df = st.session_state.log_output_df.iloc[:-n_log].reset_index(drop=True)

        # Restore Processing Status in master_df to blank
        undo_master_idx = df.index[snap['prev_index']]
        st.session_state.master_df.at[undo_master_idx, 'Processing Status'] = ''
        st.session_state.master_df.at[undo_master_idx, 'Notes']             = snap['notes']

        st.success("Last entry undone. You can re-edit and resubmit.")
        st.rerun()

    # --- Output Previews ---
    with st.expander("📋 Log Output Preview", expanded=False):
        if st.session_state.log_output_df.empty:
            st.caption("No logs submitted yet.")
        else:
            st.dataframe(st.session_state.log_output_df, use_container_width=True)

    with st.expander("📋 Master Output Preview", expanded=False):
        if st.session_state.master_output_df.empty:
            st.caption("No wells processed yet.")
        else:
            st.dataframe(st.session_state.master_output_df, use_container_width=True)
