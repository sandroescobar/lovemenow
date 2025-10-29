# Discount Usage Database Fix

## Problem
Production was failing with: `Unknown column 'created_at' in 'field list'` when users applied discount codes during checkout.

### Root Cause
- The `DiscountUsage` model was updated to include a `created_at` column (models.py line 456)
- Local development works because `db.create_all()` creates tables from scratch with all columns
- Production database had the old schema without the `created_at` column
- The old `add_created_at_to_discount_usages.py` migration script was never run on production

## Solution
A new automatic migration system has been implemented that:

### 1. **Automatic Schema Migrations** (`database_migrations.py`)
   - Runs automatically on app startup
   - Checks if `discount_usages.created_at` column exists
   - Adds it if missing with `CURRENT_TIMESTAMP` default
   - Non-blocking - errors are logged but don't crash the app

### 2. **Integration into App Startup** (app.py lines 173-183)
   - Migrations run in the `create_app()` function
   - Runs for both production (wsgi.py) and development (main.py)
   - Wraps in try/except to prevent startup failures

## What Changed
1. **NEW**: `database_migrations.py` - Automatic schema repair system
2. **UPDATED**: `app.py` - Calls migration system on app startup
3. **DEPRECATED**: `add_created_at_to_discount_usages.py` - No longer needed (kept for reference)

## How It Works

```python
# On app startup:
from database_migrations import run_all_migrations
run_all_migrations(db, app)

# This function:
# 1. Checks if discount_usages table has created_at column
# 2. If missing, runs: ALTER TABLE discount_usages ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP
# 3. Logs the action
# 4. Commits the change
```

## Deployment Steps

### For Render/Production
1. Push the code with the new `database_migrations.py` and updated `app.py`
2. The migration will run automatically on app startup
3. Check logs for "Database migrations complete" message
4. Done! The schema will be fixed automatically

### For Local Development
1. No action needed - migrations run automatically
2. Check console output for migration messages

## Testing

After deployment, verify the fix by:

```sql
-- This should now succeed (column exists)
SELECT created_at FROM discount_usages LIMIT 1;

-- Also verify no test user is blocked
-- Try a purchase with a discount code
```

## Future Migrations

To add new migrations:
1. Create a new function in `database_migrations.py` named `ensure_<table>_<column>(db)`
2. Add it to the `migrations` list in `run_all_migrations()`
3. It will run automatically on next app startup

Example:
```python
def ensure_users_some_new_column(db):
    try:
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('users')]
        
        if 'some_new_column' not in columns:
            logger.warning("⚠️  Missing column - FIXING...")
            db.session.execute(text("""
                ALTER TABLE users
                ADD COLUMN some_new_column VARCHAR(100) DEFAULT 'default_value'
            """))
            db.session.commit()
            logger.info("✅ Added column")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return False
```

## Notes
- All migrations are **idempotent** - they won't fail if run multiple times
- Errors are logged but don't crash the app
- This is a temporary solution; consider using Alembic for formal migrations in the future