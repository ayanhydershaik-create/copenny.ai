"""
Comprehensive data sync diagnostic - run this from CoPenny.Ai root dir.
"""
import os, sys
sys.path.insert(0, os.path.abspath("."))

USER_ID = "8LHc6JLobCg5jNW13BrixmxnSPa2"

print("=== CO PENNY DATA SYNC DIAGNOSTIC ===\n")

# 1. Check what normalize_user_id produces
from app.tools.csv_tools import normalize_user_id
safe_id = normalize_user_id(USER_ID)
print(f"1. normalize_user_id('{USER_ID}') = '{safe_id}'")

# 2. Check paths
BASE_DIR = os.path.abspath(".")
user_data_dir = os.path.join(BASE_DIR, "state", "models", "user_data")
save_path = os.path.join(user_data_dir, safe_id, "transactions.csv")
print(f"\n2. Expected save path:\n   {save_path}")
print(f"   File exists: {os.path.exists(save_path)}")

# 3. Check all files in user_data dir
print(f"\n3. All files in {user_data_dir}:")
if os.path.exists(user_data_dir):
    for root, dirs, files in os.walk(user_data_dir):
        level = root.replace(user_data_dir, "").count(os.sep)
        indent = "  " * level
        print(f"{indent}{os.path.basename(root)}/")
        for f in files:
            full = os.path.join(root, f)
            size_kb = os.path.getsize(full) / 1024
            print(f"{indent}  {f} ({size_kb:.1f} KB)")
else:
    print("  [DIRECTORY DOES NOT EXIST!]")

# 4. Test get_user_csv_path
from app.tools.enhanced_csv_tools import get_user_csv_path
resolved = get_user_csv_path(USER_ID)
print(f"\n4. get_user_csv_path('{USER_ID}') = {resolved}")

# 5. Test load_user_data_smart
from app.tools.enhanced_csv_tools import load_user_data_smart
df = load_user_data_smart(USER_ID)
if df is not None:
    print(f"\n5. load_user_data_smart: loaded {len(df)} rows")
    print(f"   Columns: {df.columns.tolist()}")
    if 'amount' in df.columns:
        print(f"   Expenses (amount<0): {len(df[df['amount'] < 0])}")
        print(f"   Income (amount>0): {len(df[df['amount'] > 0])}")
else:
    print("\n5. load_user_data_smart: RETURNED NONE - CSV NOT FOUND OR EMPTY")

# 6. Check the analytics engine
from app.services.analytics_service import AnalyticsEngine
engine = AnalyticsEngine()
metrics = engine.calculate_metrics(USER_ID)
print(f"\n6. AnalyticsEngine.calculate_metrics:")
print(f"   has_data: {metrics.get('has_data')}")
print(f"   topSpendingCategory: {metrics.get('topSpendingCategory')}")
print(f"   potentialSavings: {metrics.get('potentialSavings')}")
print(f"   financialHealthScore: {metrics.get('financialHealthScore')}")

# 7. Check what the validate_csv says about the user's actual CSV
if resolved:
    from app.tools.personalization import PersonalizationEngine
    pe = PersonalizationEngine()
    validation = pe.validate_csv(resolved)
    print(f"\n7. validate_csv result:")
    print(f"   valid: {validation.get('valid')}")
    print(f"   error: {validation.get('error')}")
    print(f"   date_column: {validation.get('date_column')}")
    print(f"   amount_column: {validation.get('amount_column')}")
    print(f"   category_column: {validation.get('category_column')}")
else:
    print("\n7. Cannot run validate_csv - no CSV file found!")

print("\n=== DIAGNOSTIC COMPLETE ===")
