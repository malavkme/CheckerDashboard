import streamlit as st
import pymysql
import pandas as pd
from datetime import datetime

# ---------- DB CONNECTION ----------
def get_connection():
    return pymysql.connect(
        host="0.tcp.in.ngrok.io",
        port=12055,
        user="pyuser",
        password="admin",
        database="invoiceapp",
        cursorclass=pymysql.cursors.DictCursor
    )

# ---------- FETCH DATA ----------
def get_pending_transactions():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM t_parenttransactions WHERE Status = 'P'")
        rows = cur.fetchall()
    conn.close()
    return rows

def get_ledgers():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM m_ledger")
        rows = cur.fetchall()
    conn.close()
    return rows

def insert_transaction(parent_srno, ledger_acc, amount, dc):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO t_transactions (LedgerNumber, Amount, `D/C`, ParentSrNo, LogDateTime)
               VALUES (%s, %s, %s, %s, %s)""",
            (ledger_acc, amount, dc, parent_srno, datetime.now())
        )
    conn.commit()
    conn.close()

def update_parent_status(srno, status):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("UPDATE t_parenttransactions SET Status=%s WHERE SrNo=%s", (status, srno))
    conn.commit()
    conn.close()

# ---------- STREAMLIT UI ----------
st.set_page_config(page_title="Checker Dashboard", layout="wide")

st.title("🔍 Checker Dashboard – Confirm Pending Transactions")

pending = get_pending_transactions()
ledgers = get_ledgers()
ledgers_df = pd.DataFrame(ledgers)

if not pending:
    st.success("✅ No pending transactions.")
else:
    for txn in pending:
        st.subheader(f"Transaction #{txn['SrNo']} | Amount: {txn['Amount']} | Narration: {txn['Narration']}")
        category = txn.get("Category", None)

        # --- Debit account selection (filter by category) ---
        if category:
            debit_options = ledgers_df[ledgers_df["Category"] == category]
        else:
            debit_options = ledgers_df

        debit_choice = st.selectbox(
            f"Select Debit Account for Txn {txn['SrNo']}",
            options=debit_options["Name"].tolist(),
            key=f"debit_{txn['SrNo']}"
        )

        # --- Credit account logic ---
        if txn.get("Type") == "Cash":
            credit_options = ledgers_df[ledgers_df["Category"].str.lower() == "cash"]
        else:
            # try to find vendor by GST+Name
            vendor_match = ledgers_df[
                (ledgers_df["Name"].str.lower() == txn["Narration"].lower()) |
                (ledgers_df["GSTN"].notna())
            ]
            credit_options = vendor_match if not vendor_match.empty else ledgers_df

        credit_choice = st.selectbox(
            f"Select Credit Account for Txn {txn['SrNo']}",
            options=credit_options["Name"].tolist(),
            key=f"credit_{txn['SrNo']}"
        )

        # Confirm Button
        if st.button(f"✅ Confirm Transaction {txn['SrNo']}", key=f"confirm_{txn['SrNo']}"):
            # Get Ledger Numbers
            debit_acc = ledgers_df.loc[ledgers_df["Name"] == debit_choice, "LedgerAccNo"].values[0]
            credit_acc = ledgers_df.loc[ledgers_df["Name"] == credit_choice, "LedgerAccNo"].values[0]

            # Insert both legs
            insert_transaction(txn["SrNo"], debit_acc, txn["Amount"], "D")
            insert_transaction(txn["SrNo"], credit_acc, txn["Amount"], "C")

            # Update Parent Status
            update_parent_status(txn["SrNo"], "UC")

            st.success(f"Transaction {txn['SrNo']} confirmed and posted ✅")
