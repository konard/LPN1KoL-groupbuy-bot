"""
Experiment: Verify that chat/models.py index names now match 0001_initial.py

This script confirms that:
1. 0001_initial.py uses explicit custom names for indexes
2. models.py now also uses the SAME explicit names
3. Therefore makemigrations will detect NO difference -> no 0002 rename migration

ROOT CAUSE:
- 0001_initial.py had custom fake names: chat_messa_procure_a1b2c3_idx, etc.
- models.py had NO explicit names -> Django would auto-generate different names
- Django's makemigrations (run in entrypoint.sh) detected this mismatch
- It generated a 0002 rename migration
- On fresh DBs, this rename fails: "relation chat_messa_procure_a1b2c3_idx does not exist"
  because the DB was initialized from the OLD models.py with auto-generated names

FIX:
- Added explicit names to models.py that MATCH what 0001_initial.py uses
- Now migration state and model state are consistent
- makemigrations finds no difference -> no 0002 rename migration generated
"""

import re

MODELS_PY = "core/chat/models.py"
MIGRATION_01 = "core/chat/migrations/0001_initial.py"

# Read both files
with open(MODELS_PY) as f:
    models_content = f.read()

with open(MIGRATION_01) as f:
    migration_content = f.read()

# Extract index names from models.py
model_names = set(re.findall(r"name='([^']+)'", models_content))

# Extract index names from 0001_initial.py
migration_names = set(re.findall(r"name='([^']+)'", migration_content))

print("=== Index Name Consistency Check ===\n")
print(f"Names in models.py:       {sorted(model_names)}")
print(f"Names in 0001_initial.py: {sorted(migration_names)}")
print()

if model_names == migration_names:
    print("✓ PASS: Both files use identical index names.")
    print("  Django makemigrations will detect NO mismatch -> no 0002 rename migration!")
else:
    only_in_models = model_names - migration_names
    only_in_migration = migration_names - model_names
    if only_in_models:
        print(f"✗ FAIL: Names only in models.py: {only_in_models}")
    if only_in_migration:
        print(f"✗ FAIL: Names only in 0001_initial.py: {only_in_migration}")

print()
print("=== Verifying names match between model and migration ===")
expected_pairs = [
    ("chat_messa_procure_a1b2c3_idx", "Message.indexes[0]: ['procurement', 'created_at']"),
    ("chat_messa_user_id_d4e5f6_idx", "Message.indexes[1]: ['user']"),
    ("notificati_user_id_g7h8i9_idx", "Notification.indexes[0]: ['user', 'is_read']"),
    ("notificati_created_j0k1l2_idx", "Notification.indexes[1]: ['created_at']"),
]
for name, description in expected_pairs:
    in_models = name in models_content
    in_migration = name in migration_content
    status = "✓" if (in_models and in_migration) else "✗"
    print(f"  {status} {name} ({description})")
    if not in_models:
        print(f"     MISSING from models.py!")
    if not in_migration:
        print(f"     MISSING from 0001_initial.py!")
